import { Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Wizard from "./pages/Wizard";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/start" element={<Wizard />} />
    </Routes>
  );
}
