export const CHAT_STORAGE_KEY = 'risk-analyzer-chats-v1';
export const CHAT_GREETING = 'Hello! How can I help you today?';
const LEGACY_GREETING = 'Hello! Ask me a general question or about available applications, reports, and portfolio data. No selection or upload is needed. I am read-only and cannot change data.';

export function createChat(applicationId = null) {
  return {
    id: crypto.randomUUID(),
    title: 'New chat',
    applicationId,
    messages: [{ sender: 'assistant', text: CHAT_GREETING }],
    history: [],
    updatedAt: Date.now(),
  };
}

function isSavedChat(chat) {
  return chat && typeof chat.id === 'string' && chat.id.length > 0
    && typeof chat.title === 'string' && chat.title.length > 0
    && (chat.applicationId === null || typeof chat.applicationId === 'string')
    && Number.isFinite(chat.updatedAt)
    && Array.isArray(chat.messages) && chat.messages.length > 0
    && chat.messages.every((message) => message
      && ['user', 'assistant'].includes(message.sender)
      && typeof message.text === 'string'
      && (message.language == null || (
        typeof message.language === 'string' && message.language.length <= 35
        && /^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$/.test(message.language)
      ))
      && (message.error === undefined || typeof message.error === 'boolean'))
    && Array.isArray(chat.history) && chat.history.length <= 6
    && chat.history.every((turn) => turn
      && typeof turn.user_msg === 'string' && turn.user_msg.trim().length > 0 && turn.user_msg.length <= 4000
      && typeof turn.assistant_msg === 'string' && turn.assistant_msg.length > 0 && turn.assistant_msg.length <= 16000);
}

export function loadChatState(applicationId = null) {
  const initialChat = createChat(applicationId);
  const initialState = {
    chats: [initialChat],
    activeChatId: initialChat.id,
    storageError: '',
    persistenceEnabled: true,
  };
  try {
    const saved = window.localStorage.getItem(CHAT_STORAGE_KEY);
    if (saved === null) return initialState;
    const parsed = JSON.parse(saved);
    if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.chats)
      || parsed.chats.length === 0 || !parsed.chats.every(isSavedChat)
      || new Set(parsed.chats.map((chat) => chat.id)).size !== parsed.chats.length
      || !parsed.chats.some((chat) => chat.id === parsed.activeChatId)) {
      throw new Error('Invalid saved chat format');
    }
    const chats = parsed.chats.map((chat) => {
      const messages = chat.messages.map((message, index) => (
        index === 0 && message.sender === 'assistant' && message.text === LEGACY_GREETING
          ? { ...message, text: CHAT_GREETING }
          : message
      ));
      if (messages.at(-1).sender !== 'user') return { ...chat, messages };
      return {
        ...chat,
        messages: [...messages, {
          sender: 'assistant',
          text: 'The previous response was interrupted when this page closed. Please send your question again.',
          error: true,
        }],
      };
    });
    return { ...initialState, chats, activeChatId: parsed.activeChatId };
  } catch {
    console.error('Saved chat history could not be loaded.');
    return {
      ...initialState,
      persistenceEnabled: false,
      storageError: 'Saved chats could not be loaded. Existing storage was not changed. New messages will only be kept until this page closes.',
    };
  }
}

export function saveChatState(chats, activeChatId) {
  window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify({ version: 1, chats, activeChatId }));
}

export function updateChat(chats, chatId, update, moveToTop = false) {
  const index = chats.findIndex((chat) => chat.id === chatId);
  if (index === -1) throw new Error('The conversation is no longer available.');
  const updated = update(chats[index]);
  if (moveToTop) return [updated, ...chats.slice(0, index), ...chats.slice(index + 1)];
  return chats.map((chat, position) => position === index ? updated : chat);
}

export function removeChat(state, chatId, replacementChat) {
  if (!state.chats.some((chat) => chat.id === chatId)) {
    throw new Error('The conversation is no longer available.');
  }
  const remaining = state.chats.filter((chat) => chat.id !== chatId);
  if (!remaining.length) remaining.push(replacementChat || createChat());
  return {
    ...state,
    chats: remaining,
    activeChatId: state.activeChatId === chatId ? remaining[0].id : state.activeChatId,
  };
}
