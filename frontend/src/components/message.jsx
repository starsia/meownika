import "../App.css";
import { useEffect, useState } from "react";
import { TodoForm } from "../components/TodoForm";
import { TodoList } from "../components/TodoList";

import axios from "axios"; // import here

const [todos, setTodos] = useState([]);

// function to fetch all messages from BE
useEffect(() => {
    axios
      .get("http://localhost:8000/messages")
      .then((response) => {
        setTodos(response.data);
      })
      .catch((error) => {
        console.log("There was an error retrieving the message list: ", error);
      });
  }, []);


useEffect(() => {
// Function to fetch todos
const fetchTodos = async () => {
    try {
    const response = await axios.get("http://localhost:8000/messages");
    setTodos(response.data); // Update the todos state with fetched data
    } catch (error) {
    console.error("There was an error fetching the todos:", error);
    }
};

fetchTodos();
}, []);