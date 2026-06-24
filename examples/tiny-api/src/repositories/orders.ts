export const orderRepository = {
  save: (order: { status: string }) => database.orders.insert(order),
};
