import express from "express";
import { acceptOrder } from "./services/orders";

const app = express();

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.post("/orders", (_req, res) => {
  const order = acceptOrder();
  res.status(202).json(order);
});

app.listen(3000);
