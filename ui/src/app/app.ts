import { CommonModule } from '@angular/common';
import { Component, ElementRef, ViewChild, computed, effect, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Renderer, Tokens, marked } from 'marked';

type MessageRole = 'user' | 'assistant';
type MessageState = 'streaming' | 'complete' | 'interrupted' | 'error';

interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  state: MessageState;
  interrupt?: PendingInterrupt;
  interruptResponding?: boolean;
}

interface InterruptRequest {
  id?: string;
  question: string;
  operation?: string;
  query?: string;
  params?: unknown;
  instructions?: string;
}

interface InterruptGroup {
  id?: string;
  agent?: string;
  threadId?: string;
  requests: InterruptRequest[];
}

interface PendingInterrupt {
  prompt: string;
  groups: InterruptGroup[];
}

interface SseEvent {
  type: string;
  data: unknown;
}

interface ApiError {
  code?: string;
  message?: string;
}

type AgentRequest = { thread_id: string; message: string } | { thread_id: string; resume: string };

const API_URL = '/api/v1/agent/stream';
const THREAD_ID_SESSION_KEY = 'agent-ui.thread-id';

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  @ViewChild('conversation') private conversation?: ElementRef<HTMLElement>;
  @ViewChild('messageInput') private messageInput?: ElementRef<HTMLTextAreaElement>;

  protected readonly messages = signal<ChatMessage[]>([]);
  protected readonly draft = signal('');
  protected readonly isStreaming = signal(false);
  protected readonly connectionLabel = signal('Pronto');
  protected readonly threadId = signal(this.getOrCreateThreadId());
  protected readonly pendingInterrupt = computed(() =>
    this.messages().find((message) => message.state === 'interrupted' && message.interrupt),
  );

  private abortController?: AbortController;
  private readonly markdownRenderer = new Renderer();

  constructor() {
    this.markdownRenderer.link = ({ href, title, tokens }: Tokens.Link) => {
      const label = this.markdownRenderer.parser.parseInline(tokens);
      const safeHref = this.escapeAttribute(href);
      const safeTitle = title ? ` title="${this.escapeAttribute(title)}"` : '';
      return `<a class="markdown-link" href="${safeHref}"${safeTitle} target="_blank" rel="noopener noreferrer">${label}<span class="link-icon" aria-hidden="true">↗</span></a>`;
    };

    marked.setOptions({
      breaks: true,
      gfm: true,
      renderer: this.markdownRenderer,
    });

    effect(() => {
      this.messages();
      queueMicrotask(() => this.scrollToBottom());
    });
  }

  protected renderMarkdown(content: string): string {
    return marked.parse(content) as string;
  }

  protected onInput(event: Event): void {
    const textarea = event.target as HTMLTextAreaElement;
    this.draft.set(textarea.value);
    this.resizeTextarea(textarea);
  }

  protected onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      void this.sendMessage();
    }
  }

  protected async sendMessage(messageOverride?: string): Promise<void> {
    const message = (messageOverride ?? this.draft()).trim();
    if (!message || this.isStreaming()) return;

    const interruptedMessage = this.pendingInterrupt();
    let sentAsResume = Boolean(interruptedMessage);
    let requestBody: AgentRequest = interruptedMessage
      ? { thread_id: this.threadId(), resume: message }
      : { thread_id: this.threadId(), message };

    if (interruptedMessage) {
      this.setInterruptResponding(interruptedMessage.id, true);
    }

    this.draft.set('');
    this.resetTextarea();

    const userMessage: ChatMessage = {
      id: this.createId(),
      role: 'user',
      content: message,
      state: 'complete',
    };
    const assistantMessage: ChatMessage = {
      id: this.createId(),
      role: 'assistant',
      content: '',
      state: 'streaming',
    };

    this.messages.update((items) => [...items, userMessage, assistantMessage]);
    this.isStreaming.set(true);
    this.connectionLabel.set('Respondendo');
    this.abortController = new AbortController();

    try {
      let response = await this.postAgentRequest(requestBody);

      if (!response.ok) {
        const apiError = await this.readApiError(response);
        if (apiError.code === 'checkpoint_requires_resume' && !sentAsResume) {
          requestBody = { thread_id: this.threadId(), resume: message };
          sentAsResume = true;
          response = await this.postAgentRequest(requestBody);
        } else {
          throw this.apiResponseError(response.status, apiError);
        }
      }

      if (!response.ok) {
        throw this.apiResponseError(response.status, await this.readApiError(response));
      }
      if (!response.body) {
        throw new Error('A API não retornou um fluxo de resposta.');
      }

      if (interruptedMessage) {
        this.resolveInterrupt(interruptedMessage.id);
      }

      await this.consumeStream(response.body, assistantMessage.id);
      this.finishMessageIfNeeded(assistantMessage.id);
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        this.updateMessage(assistantMessage.id, (item) => ({
          ...item,
          state: 'complete',
          content: item.content || 'Resposta interrompida.',
        }));
      } else {
        if (interruptedMessage) {
          this.setInterruptResponding(interruptedMessage.id, false);
        }
        const detail = error instanceof Error ? error.message : 'Erro inesperado.';
        this.setMessageError(assistantMessage.id, `Não foi possível obter uma resposta. ${detail}`);
      }
    } finally {
      this.isStreaming.set(false);
      this.connectionLabel.set(this.pendingInterrupt() ? 'Aguardando confirmação' : 'Pronto');
      this.abortController = undefined;
      queueMicrotask(() => this.messageInput?.nativeElement.focus());
    }
  }

  protected stopStreaming(): void {
    this.abortController?.abort();
  }

  protected respondToInterrupt(messageId: string, approved: boolean): void {
    if (this.pendingInterrupt()?.id !== messageId) return;
    void this.sendMessage(approved ? 'sim' : 'não');
  }

  protected formatParams(params: unknown): string {
    if (typeof params === 'string') return params;
    try {
      return JSON.stringify(params, null, 2);
    } catch {
      return String(params);
    }
  }

  protected trackMessage(_index: number, message: ChatMessage): string {
    return message.id;
  }

  private async consumeStream(
    stream: ReadableStream<Uint8Array>,
    messageId: string,
  ): Promise<void> {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });

      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? '';

      for (const block of blocks) {
        const event = this.parseSseBlock(block);
        if (event) this.handleEvent(event, messageId);
      }

      if (done) {
        if (buffer.trim()) {
          const event = this.parseSseBlock(buffer);
          if (event) this.handleEvent(event, messageId);
        }
        break;
      }
    }
  }

  private parseSseBlock(block: string): SseEvent | null {
    let type = 'message';
    const data: string[] = [];

    for (const line of block.split(/\r?\n/)) {
      if (!line || line.startsWith(':')) continue;
      const separator = line.indexOf(':');
      const field = separator === -1 ? line : line.slice(0, separator);
      let value = separator === -1 ? '' : line.slice(separator + 1);
      if (value.startsWith(' ')) value = value.slice(1);

      if (field === 'event') type = value;
      if (field === 'data') data.push(value);
    }

    if (!data.length) return null;
    const rawData = data.join('\n');
    const parsedData = this.parseJson(rawData);

    if (type === 'message' && this.isRecord(parsedData)) {
      const embeddedType = parsedData['event'] ?? parsedData['type'];
      if (typeof embeddedType === 'string') type = embeddedType;
    }

    return { type: type.toLowerCase(), data: parsedData };
  }

  private handleEvent(event: SseEvent, messageId: string): void {
    switch (event.type) {
      case 'metadata': {
        const receivedThreadId = this.findString(event.data, ['thread_id', 'threadId']);
        if (receivedThreadId) this.setThreadId(receivedThreadId);
        break;
      }
      case 'token': {
        if (!this.isVisibleAssistantToken(event.data)) break;
        const token = this.extractText(event.data);
        if (token) {
          this.updateMessage(messageId, (item) => ({
            ...item,
            content: item.content + token,
          }));
        }
        break;
      }
      case 'final': {
        const finalText = this.extractText(event.data);
        this.updateMessage(messageId, (item) => ({
          ...item,
          content: finalText || item.content,
          state: 'complete',
        }));
        break;
      }
      case 'interrupt': {
        const interrupt = this.parseInterrupt(event.data);
        const receivedThreadId = this.findDirectString(event.data, ['thread_id', 'threadId']);
        if (receivedThreadId) this.setThreadId(receivedThreadId);
        this.updateMessage(messageId, (item) => ({
          ...item,
          // Tokens anteriores ao interrupt são etapas intermediárias (por exemplo,
          // resultados de ferramentas), não uma resposta final do assistente.
          content: '',
          interrupt,
          state: 'interrupted',
        }));
        this.connectionLabel.set('Aguardando confirmação');
        break;
      }
      case 'error': {
        this.setMessageError(messageId, this.extractText(event.data) || 'A API retornou um erro.');
        break;
      }
      case 'done':
        this.finishMessageIfNeeded(messageId);
        break;
      default: {
        // Alguns servidores enviam tokens sem declarar explicitamente o evento.
        const text = this.extractText(event.data);
        if (text && event.type === 'message') {
          this.updateMessage(messageId, (item) => ({
            ...item,
            content: item.content + text,
          }));
        }
      }
    }
  }

  private extractText(value: unknown): string {
    if (typeof value === 'string') return value === '[DONE]' ? '' : value;
    if (Array.isArray(value)) {
      for (const item of value) {
        const nested = this.extractText(item);
        if (nested) return nested;
      }
      return '';
    }
    if (!this.isRecord(value)) return '';

    for (const key of [
      'token',
      'content',
      'text',
      'message',
      'delta',
      'answer',
      'response',
      'detail',
      'prompt',
      'question',
      'value',
      'data',
      'interrupts',
    ]) {
      const candidate = value[key];
      if (typeof candidate === 'string') return candidate;
      if (this.isRecord(candidate) || Array.isArray(candidate)) {
        const nested = this.extractText(candidate);
        if (nested) return nested;
      }
    }
    return '';
  }

  private parseInterrupt(value: unknown): PendingInterrupt {
    const fallback = 'O assistente precisa da sua confirmação para continuar.';
    const event = this.isRecord(value) ? value : {};
    const rawInterrupts = Array.isArray(event['interrupts']) ? event['interrupts'] : [value];
    const groups = rawInterrupts.map((item) => this.parseInterruptGroup(item, fallback));
    const firstQuestion = groups.flatMap((group) => group.requests)[0]?.question;

    return {
      prompt: firstQuestion || fallback,
      groups,
    };
  }

  private parseInterruptGroup(value: unknown, fallback: string): InterruptGroup {
    const outer = this.isRecord(value) ? value : {};
    const payload = this.isRecord(outer['value']) ? outer['value'] : outer;
    const rawRequests = Array.isArray(payload['requests'])
      ? payload['requests']
      : [this.isRecord(outer['value']) ? outer['value'] : value];

    return {
      id: this.stringValue(outer['id']),
      agent: this.stringValue(payload['agent']),
      threadId: this.stringValue(payload['thread_id'] ?? payload['threadId']),
      requests: rawRequests.map((request) => this.parseInterruptRequest(request, fallback)),
    };
  }

  private parseInterruptRequest(value: unknown, fallback: string): InterruptRequest {
    if (typeof value === 'string') {
      return { question: value || fallback };
    }

    const request = this.isRecord(value) ? value : {};
    const payload = this.isRecord(request['value']) ? request['value'] : request;
    const plainValue = typeof request['value'] === 'string' ? request['value'] : undefined;

    return {
      id: this.stringValue(request['id']),
      question: this.stringValue(payload['question']) ?? plainValue ?? fallback,
      operation: this.stringValue(payload['operation']),
      query: this.stringValue(payload['query']),
      params: payload['params'],
      instructions: this.stringValue(payload['instructions']),
    };
  }

  private stringValue(value: unknown): string | undefined {
    return typeof value === 'string' && value ? value : undefined;
  }

  private findDirectString(value: unknown, keys: string[]): string | undefined {
    if (!this.isRecord(value)) return undefined;
    for (const key of keys) {
      const candidate = value[key];
      if (typeof candidate === 'string') return candidate;
    }
    return undefined;
  }

  private isVisibleAssistantToken(value: unknown): boolean {
    const agent = this.findDirectString(value, ['agent']);
    const node = this.findDirectString(value, ['node']);
    return (!agent || agent === 'root') && (!node || node === 'llm_node');
  }

  private findString(value: unknown, keys: string[]): string | undefined {
    if (!this.isRecord(value)) return undefined;
    for (const key of keys) {
      if (typeof value[key] === 'string') return value[key];
    }
    for (const nested of Object.values(value)) {
      const result = this.findString(nested, keys);
      if (result) return result;
    }
    return undefined;
  }

  private parseJson(value: string): unknown {
    try {
      return JSON.parse(value);
    } catch {
      return value;
    }
  }

  private isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
  }

  private async postAgentRequest(body: AgentRequest): Promise<Response> {
    return fetch(API_URL, {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      signal: this.abortController?.signal,
    });
  }

  private async readApiError(response: Response): Promise<ApiError> {
    try {
      const payload: unknown = await response.json();
      if (!this.isRecord(payload) || !this.isRecord(payload['error'])) return {};
      return {
        code: this.stringValue(payload['error']['code']),
        message: this.stringValue(payload['error']['message']),
      };
    } catch {
      return {};
    }
  }

  private apiResponseError(status: number, apiError: ApiError): Error {
    const detail = apiError.message ?? `A API respondeu com o status ${status}.`;
    return new Error(detail);
  }

  private getOrCreateThreadId(): string {
    try {
      const storedThreadId = sessionStorage.getItem(THREAD_ID_SESSION_KEY);
      if (storedThreadId) return storedThreadId;

      const threadId = `conversation-${this.createId()}`;
      sessionStorage.setItem(THREAD_ID_SESSION_KEY, threadId);
      return threadId;
    } catch {
      return `conversation-${this.createId()}`;
    }
  }

  private setThreadId(threadId: string): void {
    this.threadId.set(threadId);
    try {
      sessionStorage.setItem(THREAD_ID_SESSION_KEY, threadId);
    } catch {
      // A conversa continua em memória quando o armazenamento da sessão está indisponível.
    }
  }

  private setMessageError(messageId: string, detail: string): void {
    this.updateMessage(messageId, (item) => ({
      ...item,
      state: 'error',
      content: detail,
    }));
  }

  private setInterruptResponding(messageId: string, responding: boolean): void {
    this.updateMessage(messageId, (item) => ({
      ...item,
      interruptResponding: responding,
    }));
  }

  private resolveInterrupt(messageId: string): void {
    this.updateMessage(messageId, (item) => ({
      ...item,
      state: 'complete',
      interruptResponding: undefined,
    }));
  }

  private finishMessageIfNeeded(messageId: string): void {
    this.updateMessage(messageId, (item) =>
      item.state === 'streaming'
        ? {
            ...item,
            state: 'complete',
            content: item.content || 'A resposta foi concluída sem conteúdo.',
          }
        : item,
    );
  }

  private updateMessage(messageId: string, updater: (message: ChatMessage) => ChatMessage): void {
    this.messages.update((items) =>
      items.map((item) => (item.id === messageId ? updater(item) : item)),
    );
  }

  private createId(): string {
    return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  }

  private escapeAttribute(value: string): string {
    return value
      .replaceAll('&', '&amp;')
      .replaceAll('"', '&quot;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;');
  }

  private resizeTextarea(textarea: HTMLTextAreaElement): void {
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
  }

  private resetTextarea(): void {
    queueMicrotask(() => {
      if (this.messageInput) this.messageInput.nativeElement.style.height = 'auto';
    });
  }

  private scrollToBottom(): void {
    if (!this.conversation) return;
    const element = this.conversation.nativeElement;
    if (typeof element.scrollTo === 'function') {
      element.scrollTo({ top: element.scrollHeight, behavior: 'smooth' });
    } else {
      element.scrollTop = element.scrollHeight;
    }
  }
}
