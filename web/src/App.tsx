import { Routes, Route } from "react-router-dom";
import { MotionConfig } from "framer-motion";
import Landing from "./pages/Landing";
import Wizard from "./pages/Wizard";

export default function App() {
  // `reducedMotion="user"` makes every animation respect the visitor's
  // prefers-reduced-motion setting (transform/scroll motion is dropped).
  return (
    <MotionConfig reducedMotion="user">
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/start" element={<Wizard />} />
      </Routes>
    </MotionConfig>
  );
}
