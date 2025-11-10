"use strict";

const sentenceEl = document.getElementById("currentSentence");
const authorEl = document.getElementById("currentAuthor");
const feedbackEl = document.getElementById("feedback");
const formEl = document.getElementById("sentenceForm");

async function loadLatestSentence() {
  try {
    const response = await fetch("/api/sentence");
    if (!response.ok) {
      throw new Error(`Failed to load sentence: ${response.statusText}`);
    }
    const payload = await response.json();
    sentenceEl.textContent = payload.text;
    authorEl.textContent = payload.author;
  } catch (error) {
    console.error(error);
    sentenceEl.textContent = "Unable to load the story right now.";
    authorEl.textContent = "System";
  }
}

async function submitSentence(event) {
  event.preventDefault();
  feedbackEl.textContent = "";

  const formData = new FormData(formEl);
  const sentence = (formData.get("sentence") || "").toString().trim();
  const name = (formData.get("name") || "").toString().trim();
  const anonymous = formData.get("anonymous") === "on";

  if (!sentence) {
    feedbackEl.textContent = "Please write a sentence before submitting.";
    feedbackEl.style.color = "#f87171";
    return;
  }

  try {
    const response = await fetch("/api/sentence", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ sentence, name, anonymous }),
    });

    const contentType = response.headers.get("Content-Type") || "";
    const isJson = contentType.includes("application/json");
    const payload = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      const message =
        (isJson && payload && payload.error) ||
        (typeof payload === "string" && payload.trim()) ||
        "Server error";
      throw new Error(message);
    }

    sentenceEl.textContent = payload.text;
    authorEl.textContent = payload.author;
    feedbackEl.textContent = "Sentence added! Thanks for contributing.";
    feedbackEl.style.color = "#86efac";
    formEl.reset();
    sentenceEl.scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    console.error(error);
    const message =
      (error instanceof Error && error.message) ||
      "We couldn't save your sentence. Please try again shortly.";
    feedbackEl.textContent = message;
    feedbackEl.style.color = "#f87171";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadLatestSentence();
  formEl.addEventListener("submit", submitSentence);
});

