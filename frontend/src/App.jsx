import { useState, useEffect, useRef } from "react";
import axios from "axios";

function App() {
  const [message, setMessage] = useState("");
  const [chat, setChat] = useState([]);
  // Persisted so refreshing the tab resumes the same Claude conversation instead of starting over.
  const [sessionId, setSessionId] = useState(() => localStorage.getItem("meownika_session_id"));
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // On mount, if we have a saved session, pull its history back from the backend (Redis).
  useEffect(() => {
    if (!sessionId) return;
    axios
      .get(`http://localhost:8000/session/${sessionId}`)
      .then((res) => setChat(res.data.messages))
      .catch(() => {
        // Session may have expired (TTL) or been cleared — fall back to a fresh one.
        localStorage.removeItem("meownika_session_id");
        setSessionId(null);
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const sendMessage = async () => {
    const trimmed = message.trim();
    if (!trimmed || isLoading) return;

    setChat((prevChat) => [...prevChat, { sender: "user", text: trimmed }]);
    setMessage("");
    setIsLoading(true);

    try {
      const res = await axios.post("http://localhost:8000/cats_now/", {
        message: trimmed,
        session_id: sessionId,
      });
      const { text, images, session_id } = res.data;
      setSessionId(session_id);
      localStorage.setItem("meownika_session_id", session_id);

      setChat((prevChat) => [
        ...prevChat,
        { sender: "bot", text, images: images || [] },
      ]);
    } catch (error) {
      setChat((prevChat) => [
        ...prevChat,
        { sender: "bot", text: "Meow... something went wrong fetching a response.", images: [] },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Keep the latest message in view
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, isLoading]);

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-3 bg-gradient-to-br from-orange-400 to-red-400 px-6 py-4 text-white shadow-md">
        <span className="text-3xl leading-none" aria-hidden="true">🐱</span>
        <div>
          <h1 className="text-xl font-bold leading-tight">MeowNika</h1>
          <p className="text-sm text-white/90">Your friendly cat-photo companion</p>
        </div>
      </header>

      <main className="flex flex-1 flex-col gap-3 overflow-y-auto bg-orange-50 p-5">
        {chat.length === 0 && (
          <p className="m-auto text-center text-sm text-stone-400">
            Ask for some cats to brighten your day 🐾
          </p>
        )}

        {chat.map((entry, index) => (
          <div
            key={index}
            className={`flex ${entry.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 sm:max-w-md ${
                entry.sender === "user"
                  ? "rounded-br-md bg-red-400 text-white"
                  : "rounded-bl-md border border-orange-100 bg-white text-stone-800"
              }`}
            >
              {entry.text && <p className="whitespace-pre-wrap leading-relaxed">{entry.text}</p>}
              {(entry.images || []).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {entry.images.map((image, imgIndex) => (
                    <img
                      key={imgIndex}
                      src={`http://localhost:8000${image}`}
                      alt="Cat"
                      className="h-36 w-36 rounded-xl object-cover shadow-md"
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1 rounded-2xl rounded-bl-md border border-orange-100 bg-white px-4 py-3">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="h-2 w-2 animate-bounce rounded-full bg-stone-300"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </main>

      <footer className="flex gap-2 border-t border-orange-100 bg-white px-5 py-3.5">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about cats..."
          disabled={isLoading}
          className="flex-1 rounded-full border border-orange-200 px-4 py-2.5 outline-none transition-colors focus:border-red-400 disabled:cursor-not-allowed disabled:bg-stone-100"
        />
        <button
          onClick={sendMessage}
          disabled={isLoading || !message.trim()}
          className="rounded-full bg-red-400 px-6 py-2.5 font-semibold text-white transition-colors enabled:hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </footer>
    </div>
  );
}

export default App;
