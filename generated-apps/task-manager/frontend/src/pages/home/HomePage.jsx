```jsx
import { Routes, Route } from "react-router-dom";
import Header from "../../components/header";
import Home from "./Home";
import Login from "./Login";
import Register from "./Register";

function HomePage() {
  return (
    <>
      <Header />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      </Routes>
    </>
  );
}

export default HomePage;
```