import React, { useState } from 'react';
import { isLoggedIn } from './api/client';
import Login from './components/Login';
import Main from './components/Main';
import './App.css';

function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn());

  return (
    <div className="App">
      {loggedIn
        ? <Main onLogout={() => setLoggedIn(false)} />
        : <Login onLogin={() => setLoggedIn(true)} />
      }
    </div>
  );
}

export default App;
