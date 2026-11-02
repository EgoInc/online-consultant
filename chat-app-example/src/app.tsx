import { useEffect, useRef, useState, type FormEvent } from "react";
import { dialogueSteps, getDemoReply, type MockProduct } from "./dialogue-demo";

const apiUrl = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
const maxFileSize = 10 * 1024 * 1024;
type Page = "connection" | "dialog";
type ApiResult = { status: number; body: unknown };

function currentPage(): Page {
  return window.location.hash === "#connection" ? "connection" : "dialog";
}

function Icon({ name }: { name: "chat" | "connection" | "send" | "spark" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {name === "chat" && <path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l-3 3V11.5A7.5 7.5 0 0 1 9.5 4h3A7.5 7.5 0 0 1 20 11.5ZM7 10h8M7 14h5" />}
      {name === "connection" && <path d="m10 13 4-4M8.5 16.5l-1 1a3.5 3.5 0 0 1-5-5l4-4a3.5 3.5 0 0 1 5 0M15.5 7.5l1-1a3.5 3.5 0 0 1 5 5l-4 4a3.5 3.5 0 0 1-5 0" />}
      {name === "send" && <path d="m21 3-7 18-4-8-8-4 19-6ZM10 13 21 3" />}
      {name === "spark" && <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z" />}
    </svg>
  );
}

function ConnectionPage() {
  const [sourceType, setSourceType] = useState<"api" | "file">("api");
  const [name, setName] = useState("Магазин освещения");
  const [catalogUrl, setCatalogUrl] = useState("");
  const [productUrlTemplate, setProductUrlTemplate] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ApiResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function changeSource(value: "api" | "file") {
    setSourceType(value);
    setResult(null);
    setError(null);
  }

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return;
    setError(null);
    setResult(null);

    if (sourceType === "api") {
      try {
        const catalog = new URL(catalogUrl.trim());
        const product = new URL(productUrlTemplate.trim().replace("{id}", "example-id"));
        if (![catalog.protocol, product.protocol].every((protocol) => ["http:", "https:"].includes(protocol))) {
          throw new Error("Укажите HTTP или HTTPS ссылки.");
        }
        if (!productUrlTemplate.includes("{id}")) throw new Error("В шаблоне URL товара нужен маркер {id}.");
      } catch (caught) {
        setError(caught instanceof Error && caught.message !== "Invalid URL" ? caught.message : "Проверьте ссылки API магазина.");
        return;
      }
    } else if (!file || !/\.(xml|yml)$/i.test(file.name) || file.size === 0 || file.size > maxFileSize) {
      setError("Выберите непустой XML/YML-файл размером до 10 МиБ.");
      return;
    }

    setLoading(true);
    try {
      let body: BodyInit;
      let headers: HeadersInit | undefined;
      if (sourceType === "api") {
        headers = { "Content-Type": "application/json" };
        body = JSON.stringify({ name: name.trim(), source_type: "api", catalog_url: catalogUrl.trim(), product_url_template: productUrlTemplate.trim() });
      } else {
        const form = new FormData();
        form.append("name", name.trim());
        form.append("source_type", "file");
        form.append("file", file!);
        body = form;
      }
      const response = await fetch(`${apiUrl}/api/v1/stores`, { method: "POST", headers, body });
      const raw = await response.text();
      let responseBody: unknown;
      try {
        responseBody = JSON.parse(raw);
      } catch {
        responseBody = raw;
      }
      setResult({ status: response.status, body: responseBody });
    } catch {
      setError("Не удалось связаться с бэкендом. Проверьте, что он запущен, и повторите запрос.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section aria-labelledby="connection-title" className="connection-page">
      <header className="connection-header">
        <span className="avatar assistant-avatar" aria-hidden="true"><Icon name="connection" /></span>
        <div>
          <p className="connection-eyebrow">Кабинет ИИ-консультанта</p>
          <h1 id="connection-title">Подключение магазина</h1>
        </div>
      </header>
      <div className="connection-content">
      <p>Подключите каталог магазина через API или загрузите XML/YML.</p>
      <p className="notice">Сейчас проверяется запрос подключения. Импорт каталога ещё не реализован, товары пока не сохраняются.</p>
      <form onSubmit={(event) => void connect(event)}>
        <label htmlFor="store-name">Название магазина</label>
        <input id="store-name" value={name} maxLength={200} required disabled={loading} onChange={(event) => setName(event.target.value)} />
        <fieldset disabled={loading}>
          <legend>Источник каталога</legend>
          <div className="source-options">
            <label><input type="radio" name="source-type" value="api" checked={sourceType === "api"} onChange={() => changeSource("api")} /> API магазина</label>
            <label><input type="radio" name="source-type" value="file" checked={sourceType === "file"} onChange={() => changeSource("file")} /> Файл XML / YML</label>
          </div>
        </fieldset>
        {sourceType === "api" ? (
          <>
            <label htmlFor="catalog-url">GET URL каталога</label>
            <input id="catalog-url" type="url" placeholder="https://shop.example/api/products" value={catalogUrl} required disabled={loading} onChange={(event) => setCatalogUrl(event.target.value)} />
            <label htmlFor="product-url">Шаблон GET URL товара</label>
            <input id="product-url" type="text" placeholder="https://shop.example/api/products/{id}" value={productUrlTemplate} required disabled={loading} onChange={(event) => setProductUrlTemplate(event.target.value)} aria-describedby="api-help" />
            <p id="api-help" className="hint">В URL товара используйте {'{id}'}. Формат ответов и способ обхода страниц каталога определяет интеграция с API магазина.</p>
          </>
        ) : (
          <>
            <label htmlFor="catalog-file">Каталог магазина</label>
            <input id="catalog-file" type="file" accept=".xml,.yml,application/xml,text/xml" required disabled={loading} onChange={(event) => { setFile(event.target.files?.[0] ?? null); setResult(null); setError(null); }} aria-describedby="file-help" />
            <p id="file-help" className="hint">XML или YML, до 10 МиБ. Файл передаётся на бэкенд без разбора в браузере.</p>
          </>
        )}
        <div className="actions">
          <button type="submit" disabled={loading || !name.trim()}>{loading ? "Отправляем…" : "Отправить на подключение"}</button>
          <a href={`${apiUrl}/docs`}>Swagger API</a>
        </div>
      </form>
      {loading && <p role="status">Запрос отправляется на бэкенд…</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {result && (
        <section className="api-result" aria-labelledby="api-result-title">
          <h3 id="api-result-title">Ответ бэкенда — HTTP {result.status}</h3>
          <pre data-testid="connection-response">{typeof result.body === "string" ? result.body : JSON.stringify(result.body, null, 2)}</pre>
        </section>
      )}
      </div>
    </section>
  );
}

function ProductIllustration({ id }: { id: string }) {
  return (
    <svg viewBox="0 0 160 112" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M67 13h26M80 13v23" />
      {id === "chandelier-cloud" ? (
        <path d="M47 72c-10 0-15-7-15-15 0-9 7-16 16-16 5-11 21-13 29-4 10-13 30-8 33 7 11-2 20 5 20 15 0 8-7 13-15 13H47Z" fill="#fff" />
      ) : id === "chandelier-orbit" ? (
        <><path d="M80 36v12M45 64h70" /><ellipse cx="80" cy="64" rx="41" ry="17" /><ellipse cx="80" cy="64" rx="31" ry="10" /><path d="M44 67v10c16 17 56 17 72 0V67" /></>
      ) : id === "chandelier-star" ? (
        <><path d="M80 36v20M80 56 43 43M80 56l35-20M80 56l31 25M80 56 58 86M80 56v36" /><circle cx="40" cy="42" r="8" fill="#fff" /><circle cx="120" cy="33" r="8" fill="#fff" /><circle cx="117" cy="85" r="8" fill="#fff" /><circle cx="54" cy="91" r="8" fill="#fff" /><circle cx="80" cy="96" r="8" fill="#fff" /></>
      ) : (
        <><path d="M80 36v22M40 67c13-25 59-31 83-12M80 57l-40 10M80 57l43-2M80 57 64 85" /><circle cx="37" cy="70" r="10" fill="#fff" /><circle cx="126" cy="56" r="10" fill="#fff" /><circle cx="63" cy="89" r="10" fill="#fff" /></>
      )}
    </svg>
  );
}

const priceFormatter = new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 });

function Recommendations({ products }: { products: MockProduct[] }) {
  if (products.length === 0) return null;
  return (
    <>
      <p className="recommendation-label">Примеры товаров · демо</p>
      <ul className="recommendations" aria-label="Рекомендации товаров">
        {products.map((product) => (
          <li className="product-card" key={product.id} data-product-id={product.id}>
            <div className="product-illustration">
              {product.image_url ? <img src={product.image_url} alt={product.title} loading="lazy" decoding="async" /> : <ProductIllustration id={product.id} />}
            </div>
            <div className="product-info">
              <h2 className="product-title">{product.title}</h2>
              <p className="product-price">{product.currency === "RUB" ? priceFormatter.format(product.price) : new Intl.NumberFormat("ru-RU", { style: "currency", currency: product.currency, maximumFractionDigits: 0 }).format(product.price)}</p>
              <p className="product-description">{product.description}</p>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

function DialoguePage() {
  const [sentSteps, setSentSteps] = useState(0);
  const messagesRef = useRef<HTMLDivElement>(null);
  const nextStep = dialogueSteps[sentSteps];

  useEffect(() => {
    const messages = messagesRef.current;
    if (messages) messages.scrollTop = messages.scrollHeight;
  }, [sentSteps]);

  function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (nextStep) setSentSteps((previous) => Math.min(previous + 1, dialogueSteps.length));
  }

  return (
    <section aria-labelledby="dialog-title" className="chat-page">
      <header className="conversation-header">
        <span className="avatar assistant-avatar" aria-hidden="true">А</span>
        <div>
          <h1 id="dialog-title">Консультант</h1>
          <p className="presence">Онлайн</p>
        </div>
      </header>
      <div className="conversation-messages" ref={messagesRef} role="log" aria-label="Переписка" aria-live="polite">
        <div className="message-row incoming">
          <span className="avatar assistant-avatar" aria-hidden="true">А</span>
          <div className="message-bubble" role="group" aria-label="Консультант"><p>Здравствуйте! Помогу подобрать освещение. Что вы ищете?</p></div>
        </div>
        {dialogueSteps.slice(0, sentSteps).map((step, index) => {
          const reply = getDemoReply(index);
          return (
          <div className="exchange" key={index}>
            <div className="message-row outgoing">
              <div className="message-bubble" role="group" aria-label="Вы"><p>{step.message}</p></div>
              <span className="avatar user-avatar" aria-hidden="true">Вы</span>
            </div>
            <div className="message-row incoming">
              <span className="avatar assistant-avatar" aria-hidden="true">А</span>
              <div className="message-bubble" role="group" aria-label="Консультант">
                <p>{reply.assistantMessage}</p>
                <Recommendations products={reply.products} />
              </div>
            </div>
          </div>
          );
        })}
      </div>
      <form className="composer" onSubmit={send}>
        <textarea
          id="message"
          aria-label="Сообщение"
          rows={2}
          readOnly
          disabled={!nextStep}
          value={nextStep?.message ?? ""}
          placeholder="Диалог завершён"
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (nextStep) setSentSteps((previous) => Math.min(previous + 1, dialogueSteps.length));
            }
          }}
        />
        <button className="send-button" type="submit" disabled={!nextStep} aria-label="Отправить" title="Отправить"><Icon name="send" /></button>
      </form>
    </section>
  );
}

export function App() {
  const [page, setPage] = useState<Page>(currentPage);

  useEffect(() => {
    const onHashChange = () => setPage(currentPage());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  return (
    // Shared navigation is for the demo: the account and store chat are separate integration contexts.
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-icon"><Icon name="spark" /></span><span className="brand-label">Онлайн-консультант</span></div>
        <nav aria-label="Разделы" className="sidebar-nav">
          <a className="nav-link" href="#dialog" aria-current={page === "dialog" ? "page" : undefined}><Icon name="chat" /><span>Чат</span></a>
          <a className="nav-link" href="#connection" aria-current={page === "connection" ? "page" : undefined}><Icon name="connection" /><span>Подключение</span></a>
        </nav>
      </aside>
      <main className="workspace">
        <div className="page-container" hidden={page !== "dialog"}><DialoguePage /></div>
        <div className="page-container" hidden={page !== "connection"}><ConnectionPage /></div>
      </main>
    </div>
  );
}
