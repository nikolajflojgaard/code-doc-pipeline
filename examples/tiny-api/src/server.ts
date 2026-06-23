import express from "express";

const app = express();

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.post("/orders", (_req, res) => {
  res.status(202).json({ status: "accepted" });
});

app.listen(3000);
