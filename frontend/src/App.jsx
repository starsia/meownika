import { useState, useEffect, useRef } from "react";
import axios from "axios";

function App() {
  const [message, setMessage] = useState("");
  const [chat, setChat] = useState([]);
  const chatContainerRef = useRef(null);

  const sendMessage = async () => {
    if (!message.trim()) return;

    // Add user message to chat
    setChat((prevChat) => [...prevChat, { sender: "user", text: message }]);

    try {
      const res = await axios.post("http://localhost:8000/cats_now/", { message });
      const { text, images } = res.data;

      // Add bot response to chat
      setChat((prevChat) => [
        ...prevChat,
        { sender: "bot", text, images },
      ]);
    } catch (error) {
      setChat((prevChat) => [
        ...prevChat,
        { sender: "bot", text: "Error: Unable to fetch response.", images: [] },
      ]);
    } finally {
      setMessage("");
    }
  };

  // Scroll to the bottom of the chat container when a new message is added
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chat]);

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="bg-blue-500 text-white text-center py-4">
        <h1 className="text-xl font-bold">Cat Chatbot</h1>
      </header>

      {/* Chat Container */}
      <main
        ref={chatContainerRef}
        className="flex-grow overflow-y-scroll bg-gray-100 p-4"
      >
        {chat.map((entry, index) => (
          <div
            key={index}
            className={`mb-2 p-2 rounded ${
              entry.sender === "user" ? "bg-blue-200 text-right" : "bg-green-200 text-left"
            }`}
          >
            {entry.text && <p>{entry.text}</p>}
            {entry.images &&
              entry.images.map((image, imgIndex) => (
                <img
                  key={imgIndex}
                  src={`http://localhost:8000${image}`}
                  alt="Cat"
                  className="w-40 h-40 object-cover rounded-lg shadow-md mt-2"
                />
              ))}
          </div>
        ))}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t p-4">
        <div className="flex">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Ask about cats..."
            className="flex-grow border p-2 rounded-l"
          />
          <button
            onClick={sendMessage}
            className="p-2 bg-blue-500 text-white rounded-r"
          >
            Send
          </button>
        </div>
      </footer>
    </div>
  );
}

export default App;
