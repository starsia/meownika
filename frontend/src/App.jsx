import { useState, useEffect } from "react";
import axios from "axios";

function App() {
  const [message, setMessage] = useState("");
  const [response, setResponse] = useState("");
  const [images, setImages] = useState([]);

  // Fetch cat images from backend on load
  useEffect(() => {
    const fetchImages = async () => {
      try {
        const res = await axios.get("http://localhost:8000/get_cat_pictures");
        setImages(res.data.images);
      } catch (error) {
        console.error("Error fetching images:", error);
      }
    };

    fetchImages();
  }, []);

  const sendMessage = async () => {
    if (!message.trim()) return;
    try {
      const res = await axios.post("http://localhost:8000/cats_now/", { message });
      setResponse(JSON.stringify(res.data, null, 2));
    } catch (error) {
      setResponse("Error: Unable to fetch response.");
    }
  };

  return (
    <div className="flex flex-col items-center p-4">
      <h1 className="text-xl font-bold mb-4">Cat Chatbot</h1>
      <input
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Ask about cats..."
        className="border p-2 rounded w-80"
      />
      <button
        onClick={sendMessage}
        className="mt-2 p-2 bg-blue-500 text-white rounded"
      >
        Send
      </button>
      <pre className="mt-4 p-2 border rounded w-80 whitespace-pre-wrap">{response}</pre>

      {/* Display Images */}
      <div className="mt-4 grid grid-cols-2 gap-4">
        {images.map((src, index) => (
          <img key={index} src={`http://localhost:8000${src}`} alt={`Cat ${index + 1}`} className="w-40 h-40 object-cover rounded-lg shadow-md" />
        ))}
      </div>
    </div>
  );
}

export default App;
