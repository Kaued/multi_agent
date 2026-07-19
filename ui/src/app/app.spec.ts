import { TestBed } from '@angular/core/testing';
import { afterEach, vi } from 'vitest';
import { App } from './app';

const interruptEvent = {
  type: 'interrupt',
  thread_id: 'conversation-1',
  interrupts: [
    {
      id: '15bb7fb550038bc5b5afe92e57ec4222',
      value: {
        agent: 'postgres',
        thread_id: 'conversation-1:postgres',
        requests: [
          {
            id: 'd94d4a19390c56cd78ee961b8a1866d4',
            value: {
              question: 'Deseja executar esta alteração?',
              operation: 'INSERT',
              query: 'INSERT INTO customers (id, name, email) VALUES (:id, :name, :email)',
              params: { email: 'teste@gmail.com', id: 4, name: 'Kauê Domingues' },
              instructions: 'Responda se autoriza ou não a execução.',
            },
          },
        ],
      },
    },
  ],
};

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the assistant welcome state', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Como posso ajudar?');
  });

  it('should keep one conversation id in the current tab session', () => {
    const firstApp = TestBed.createComponent(App).componentInstance as any;
    const firstThreadId = firstApp.threadId();
    const secondApp = TestBed.createComponent(App).componentInstance as any;

    expect(firstThreadId).toMatch(/^conversation-/);
    expect(secondApp.threadId()).toBe(firstThreadId);
    expect(sessionStorage.getItem('agent-ui.thread-id')).toBe(firstThreadId);
  });

  it('should render a structured interrupt and wait for the user decision', async () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance as any;
    app.messages.set([
      {
        id: 'assistant-1',
        role: 'assistant',
        content: 'Resultado intermediário que não deve ser exibido.',
        state: 'streaming',
      },
    ]);

    app.handleEvent({ type: 'interrupt', data: interruptEvent }, 'assistant-1');
    fixture.detectChanges();
    await fixture.whenStable();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.confirmation-question')?.textContent).toContain(
      'Deseja executar esta alteração?',
    );
    expect(compiled.querySelector('.operation-badge')?.textContent).toContain('INSERT');
    expect(compiled.querySelector('.operation-details code')?.textContent).toContain(
      'INSERT INTO customers',
    );
    expect(compiled.querySelector('.operation-details pre')?.textContent).toContain(
      'teste@gmail.com',
    );
    expect(compiled.textContent).not.toContain('Resultado intermediário');
    expect(app.connectionLabel()).toBe('Aguardando confirmação');
    expect(app.pendingInterrupt()).toBeTruthy();
  });

  it('should not render specialist thoughts or tool results as assistant messages', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance as any;
    app.messages.set([{ id: 'assistant-1', role: 'assistant', content: '', state: 'streaming' }]);

    app.handleEvent(
      {
        type: 'token',
        data: {
          agent: 'postgres',
          node: 'tool_node',
          content: 'Operação recusada: resultado interno da ferramenta.',
        },
      },
      'assistant-1',
    );
    app.handleEvent(
      {
        type: 'token',
        data: { agent: 'root', node: 'llm_node', content: 'Resposta visível.' },
      },
      'assistant-1',
    );

    expect(app.messages()[0].content).toBe('Resposta visível.');
  });

  it('should resume the interrupted thread instead of sending a new message', async () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance as any;
    app.messages.set([{ id: 'assistant-1', role: 'assistant', content: '', state: 'streaming' }]);
    app.handleEvent({ type: 'interrupt', data: interruptEvent }, 'assistant-1');

    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(
          'data: {"type":"final","message":{"content":"Operação autorizada."}}\n\n' +
            'data: {"type":"done","status":"completed"}\n\n',
          { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
        ),
      );
    vi.stubGlobal('fetch', fetchMock);

    await app.sendMessage('sim');

    const [, options] = fetchMock.mock.calls[0];
    expect(JSON.parse(options.body)).toEqual({
      thread_id: 'conversation-1',
      resume: 'sim',
    });
    expect(app.pendingInterrupt()).toBeUndefined();
    expect(app.messages()[0].interrupt.groups[0].requests[0].question).toBe(
      'Deseja executar esta alteração?',
    );

    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.confirmation-question')?.textContent).toContain(
      'Deseja executar esta alteração?',
    );
    expect(fixture.nativeElement.querySelector('.confirmation-resolved')?.textContent).toContain(
      'Solicitação respondida',
    );
    expect(fixture.nativeElement.querySelector('.confirmation-actions')).toBeNull();
  });

  it('should retry as resume when the checkpoint requires it', async () => {
    sessionStorage.setItem('agent-ui.thread-id', 'conversation-session');
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance as any;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: {
              code: 'checkpoint_requires_resume',
              message: 'A thread está interrompida; envie resume em vez de message.',
            },
          }),
          { status: 409, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          'data: {"type":"final","message":{"content":"Operação retomada."}}\n\n' +
            'data: {"type":"done","status":"completed"}\n\n',
          { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
        ),
      );
    vi.stubGlobal('fetch', fetchMock);

    await app.sendMessage('sim');

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      thread_id: 'conversation-session',
      message: 'sim',
    });
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      thread_id: 'conversation-session',
      resume: 'sim',
    });
  });
});
