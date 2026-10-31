/* eslint-disable */
// Scroll Text Highlight — Originkit

import * as React from "react";
import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

const CHAR_STAGGER = 0.03;
const WORD_STAGGER = 0.08;

export default function ScrollHighlight({
  text = "Every word in this paragraph will light up as you scroll through it.",
  className = "",
  font = {},
  dimColor = "rgba(255, 255, 255, 0.2)",
  highlightColor = "#FFFFFF",
  splitBy = "words",
  scrollStart = "top 85%",
  scrollEnd = "bottom 45%",
  scrub = true,
  standalone = false,
}) {
  const containerRef = useRef(null);
  const words = text.trim().split(/\s+/).filter(Boolean);
  const chars = Array.from(text);
  const stagger = splitBy === "characters" ? CHAR_STAGGER : WORD_STAGGER;

  useEffect(() => {
    const paragraph = containerRef.current;
    if (!paragraph) return;

    const targets = paragraph.querySelectorAll(
      splitBy === "characters" ? ".char" : ".word"
    );

    const ctx = gsap.context(() => {
      gsap.set(targets, {
        color: dimColor,
      });

      gsap.to(targets, {
        color: highlightColor,
        stagger,
        scrollTrigger: {
          trigger: paragraph,
          start: scrollStart,
          end: scrollEnd,
          scrub,
        },
      });
    }, paragraph);

    return () => ctx.revert();
  }, [
    text,
    dimColor,
    highlightColor,
    splitBy,
    stagger,
    scrollStart,
    scrollEnd,
    scrub,
  ]);

  const content = (
    <p
      ref={containerRef}
      className={className}
      style={{
        margin: 0,
        display: "inline-block",
        whiteSpace: "pre-wrap",
        color: dimColor,
        ...font,
      }}
    >
      {splitBy === "characters"
        ? chars.map((char, index) => (
            <span
              key={`${char}-${index}`}
              className="char"
              style={{
                display: "inline-block",
                color: dimColor,
              }}
            >
              {char === " " ? "\u00A0" : char}
            </span>
          ))
        : words.map((word, index) => (
            <React.Fragment key={`${word}-${index}`}>
              <span
                className="word"
                style={{
                  display: "inline-block",
                  color: dimColor,
                }}
              >
                {word}
              </span>
              {index < words.length - 1 ? " " : null}
            </React.Fragment>
          ))}
    </p>
  );

  if (standalone) {
    return (
      <div style={{ paddingTop: "100dvh", paddingBottom: "100dvh" }}>
        {content}
      </div>
    );
  }

  return content;
}
