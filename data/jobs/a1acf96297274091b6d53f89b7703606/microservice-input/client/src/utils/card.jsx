// Load cart from localStorage or create a new one
export function LoadCart() {
  let cart = localStorage.getItem("cart");

  if (!cart) {
    cart = {
      orderItem: [],
    };

    console.log(cart)

    localStorage.setItem("cart", JSON.stringify(cart));
    return cart;
  }

  return JSON.parse(cart);
}

// Add item to cart or update quantity if it already exists
export function addToCart(key, qty) {
  const cart = LoadCart();
  let found = false;

  for (let i = 0; i < cart.orderItem.length; i++) {
    if (cart.orderItem[i].key === key) {
      cart.orderItem[i].qty += qty;
      found = true;
      break;
    }
  }

  if (!found) {
    cart.orderItem.push({ key, qty });
  }

  localStorage.setItem("cart", JSON.stringify(cart));
}

// Remove item from cart by key
export function removeFromCart(key) {
  const cart = LoadCart();
  cart.orderItem = cart.orderItem.filter((item) => item.key !== key);
  localStorage.setItem("cart", JSON.stringify(cart));
}
