import { orderRepository } from "../repositories/orders";

export function acceptOrder() {
  return orderRepository.save({ status: "accepted" });
}
