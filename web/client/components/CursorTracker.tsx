import React, { useEffect, useState } from "react";

export const CursorTracker = () => {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener("resize", checkMobile);

    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };

    window.addEventListener("mousemove", handleMouseMove);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("resize", checkMobile);
    };
  }, []);

  if (isMobile) return null;

  return (
    <div
      className="fixed inset-0 pointer-events-none z-[9999]"
      style={{ overflow: "hidden" }}
    >
      <div
        className="absolute w-[60px] h-[60px] bg-sky-400/20 rounded-full blur-[30px] transition-transform duration-300 ease-out"
        style={{
          left: mousePos.x,
          top: mousePos.y,
          transform: "translate(-50%, -50%)",
        }}
      />
      <div
        className="absolute w-[20px] h-[20px] bg-sky-300/30 rounded-full blur-[15px] transition-transform duration-150 ease-out"
        style={{
          left: mousePos.x,
          top: mousePos.y,
          transform: "translate(-50%, -50%)",
        }}
      />
    </div>
  );
};
