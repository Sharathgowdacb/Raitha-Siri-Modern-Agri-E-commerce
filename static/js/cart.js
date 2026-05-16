function getCookie(name) {
  const cookieValue = document.cookie
    .split('; ')
    .find((row) => row.startsWith(name + '='));
  return cookieValue ? decodeURIComponent(cookieValue.split('=')[1]) : null;
}

const cartDebounceTimers = new Map();

function showToast(message, type) {
  const container = document.getElementById('toast-container');
  if (!container) {
    return;
  }
  const toast = document.createElement('div');
  toast.className = `toast ${type === 'error' ? 'toast-error' : 'toast-success'}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(function () {
    toast.remove();
  }, 2200);
}

async function postForm(url, payload) {
  const formData = new FormData();
  Object.entries(payload).forEach(([key, value]) => {
    formData.append(key, String(value));
  });

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCookie('csrftoken') || '',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: formData,
  });

  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || 'Request failed.');
  }
  return data;
}

async function addProductToCart(addUrl, productId, quantity) {
  return postForm(addUrl, { product_id: productId, quantity: quantity });
}

async function toggleWishlist(addUrl, removeUrl, productId, inWishlist) {
  const url = inWishlist ? removeUrl.replace('/0/', `/${productId}/`) : addUrl.replace('/0/', `/${productId}/`);
  return postForm(url, {});
}

function setCheckoutEnabled(enabled) {
  const checkoutBtn = document.getElementById('checkout-btn');
  if (!checkoutBtn) {
    return;
  }

  if (enabled) {
    checkoutBtn.classList.remove('opacity-50', 'pointer-events-none');
    checkoutBtn.setAttribute('aria-disabled', 'false');
  } else {
    checkoutBtn.classList.add('opacity-50', 'pointer-events-none');
    checkoutBtn.setAttribute('aria-disabled', 'true');
  }
}

function syncCartPageEmptyState() {
  const cartRows = document.querySelectorAll('[data-cart-row-id]');
  const hasItems = cartRows.length > 0;
  const itemsSection = document.getElementById('cart-items-section');
  const emptyMessage = document.getElementById('cart-empty-message');
  const cartTotal = document.getElementById('cart-total');

  if (itemsSection && emptyMessage) {
    if (hasItems) {
      itemsSection.classList.remove('hidden');
      emptyMessage.classList.add('hidden');
    } else {
      itemsSection.classList.add('hidden');
      emptyMessage.classList.remove('hidden');
    }
  }

  if (!hasItems && cartTotal) {
    cartTotal.textContent = '0.00';
  }
  setCheckoutEnabled(hasItems);
}

function getQuantityFromInput(inputEl) {
  if (!inputEl) {
    return NaN;
  }
  const parsed = parseInt(inputEl.value || '1', 10);
  if (Number.isNaN(parsed) || parsed < 1) {
    return NaN;
  }
  return parsed;
}

async function updateCartItemRequest(btn, quantity) {
  const url = btn.dataset.updateUrl;
  if (!url || Number.isNaN(quantity)) {
    return;
  }

  const data = await postForm(url, { quantity: quantity });
  const countEl = document.getElementById('cart-count');
  if (countEl) {
    countEl.textContent = String(data.cart_count || 0);
  }

  const row = btn.closest('[data-cart-row-id]');
  if (data.removed) {
    if (row) {
      row.remove();
    }
  } else if (row) {
    const subtotalEl = row.querySelector('.cart-item-subtotal');
    if (subtotalEl) {
      subtotalEl.textContent = `₹${data.item_subtotal}`;
    }
  }

  const totalEl = document.getElementById('cart-total');
  if (totalEl && data.cart_total !== undefined) {
    totalEl.textContent = String(data.cart_total);
  }
  syncCartPageEmptyState();
}

function scheduleDebouncedCartUpdate(btn, quantity) {
  const itemId = btn.dataset.itemId;
  if (!itemId) {
    return;
  }

  if (cartDebounceTimers.has(itemId)) {
    clearTimeout(cartDebounceTimers.get(itemId));
  }

  const timer = setTimeout(async function () {
    try {
      await updateCartItemRequest(btn, quantity);
      showToast('Cart updated.', 'success');
    } catch (error) {
      showToast(error.message || 'Failed to update cart item.', 'error');
    }
  }, 350);

  cartDebounceTimers.set(itemId, timer);
}

document.addEventListener('DOMContentLoaded', function () {
  const addUrl = document.body.dataset.addToCartUrl;
  const countEl = document.getElementById('cart-count');
  const buttons = document.querySelectorAll('.add-to-cart-btn');

  if (!addUrl || !buttons.length) {
    // Continue to wire cart page controls even on pages without add-to-cart buttons.
  }

  buttons.forEach((btn) => {
    const initialLabel = btn.textContent;

    btn.addEventListener('click', async function () {
      const productId = btn.dataset.productId;
      const qtyInputId = btn.dataset.quantityInputId;
      const qtyInput = qtyInputId ? document.getElementById(qtyInputId) : null;
      const quantity = qtyInput ? parseInt(qtyInput.value || '1', 10) : 1;
      if (!productId) {
        return;
      }
      if (Number.isNaN(quantity) || quantity < 1) {
        showToast('Quantity must be at least 1.', 'error');
        return;
      }

      btn.disabled = true;
      btn.textContent = 'Adding...';

      try {
        const data = await addProductToCart(addUrl, productId, quantity);
        if (countEl) {
          countEl.textContent = String(data.cart_count || 0);
        }
        btn.textContent = 'Added';
        showToast('Added to cart.', 'success');
      } catch (error) {
        btn.textContent = 'Failed';
        showToast(error.message || 'Could not add product to cart.', 'error');
      } finally {
        setTimeout(function () {
          btn.disabled = false;
          btn.textContent = initialLabel;
        }, 900);
      }
    });
  });

  const updateButtons = document.querySelectorAll('.cart-update-btn');
  updateButtons.forEach((btn) => {
    btn.addEventListener('click', async function () {
      const qtyInputId = btn.dataset.qtyInputId;
      const qtyInput = qtyInputId ? document.getElementById(qtyInputId) : null;
      const quantity = getQuantityFromInput(qtyInput);
      if (Number.isNaN(quantity)) {
        showToast('Quantity must be at least 1.', 'error');
        return;
      }

      try {
        await updateCartItemRequest(btn, quantity);
        showToast('Cart updated.', 'success');
      } catch (error) {
        showToast(error.message || 'Failed to update cart item.', 'error');
      }
    });
  });

  const incrementButtons = document.querySelectorAll('.cart-qty-increment');
  incrementButtons.forEach((btn) => {
    btn.addEventListener('click', function () {
      const qtyInputId = btn.dataset.qtyInputId;
      const qtyInput = qtyInputId ? document.getElementById(qtyInputId) : null;
      if (!qtyInput) {
        return;
      }
      const current = parseInt(qtyInput.value || '1', 10);
      qtyInput.value = String(Number.isNaN(current) ? 1 : current + 1);
      const updateBtn = btn.closest('tr')?.querySelector('.cart-update-btn');
      if (updateBtn) {
        scheduleDebouncedCartUpdate(updateBtn, parseInt(qtyInput.value, 10));
      }
    });
  });

  const decrementButtons = document.querySelectorAll('.cart-qty-decrement');
  decrementButtons.forEach((btn) => {
    btn.addEventListener('click', function () {
      const qtyInputId = btn.dataset.qtyInputId;
      const qtyInput = qtyInputId ? document.getElementById(qtyInputId) : null;
      if (!qtyInput) {
        return;
      }
      const current = parseInt(qtyInput.value || '1', 10);
      const next = Number.isNaN(current) ? 1 : Math.max(1, current - 1);
      qtyInput.value = String(next);
      const updateBtn = btn.closest('tr')?.querySelector('.cart-update-btn');
      if (updateBtn) {
        scheduleDebouncedCartUpdate(updateBtn, next);
      }
    });
  });

  const qtyInputs = document.querySelectorAll('.cart-item-qty');
  qtyInputs.forEach((inputEl) => {
    inputEl.addEventListener('input', function () {
      const updateBtn = inputEl.closest('tr')?.querySelector('.cart-update-btn');
      const quantity = getQuantityFromInput(inputEl);
      if (!updateBtn || Number.isNaN(quantity)) {
        return;
      }
      scheduleDebouncedCartUpdate(updateBtn, quantity);
    });
  });

  const removeButtons = document.querySelectorAll('.cart-remove-btn');
  removeButtons.forEach((btn) => {
    btn.addEventListener('click', async function () {
      const url = btn.dataset.removeUrl;
      if (!url) {
        return;
      }

      try {
        const data = await postForm(url, {});
        if (countEl) {
          countEl.textContent = String(data.cart_count || 0);
        }

        const row = btn.closest('[data-cart-row-id]');
        if (row) {
          row.remove();
        }
        const totalEl = document.getElementById('cart-total');
        if (totalEl && data.cart_total !== undefined) {
          totalEl.textContent = String(data.cart_total);
        }

        syncCartPageEmptyState();
        showToast('Item removed.', 'success');
      } catch (error) {
        showToast(error.message || 'Failed to remove cart item.', 'error');
      }
    });
  });

  const wishlistButtons = document.querySelectorAll('.wishlist-btn');
  wishlistButtons.forEach((btn) => {
    btn.addEventListener('click', async function () {
      const productId = btn.dataset.productId;
      const inWishlist = btn.dataset.inWishlist === 'true';
      const addUrl = document.body.dataset.wishlistAddUrl;
      const removeUrl = document.body.dataset.wishlistRemoveUrl;

      if (!productId || !addUrl || !removeUrl) {
        return;
      }

      const icon = btn.querySelector('i');
      if (icon) {
        icon.classList.add('fa-spinner', 'fa-spin');
      }
      btn.disabled = true;

      try {
        await toggleWishlist(addUrl, removeUrl, productId, inWishlist);
        btn.dataset.inWishlist = inWishlist ? 'false' : 'true';
        if (icon) {
          if (inWishlist) {
            icon.classList.remove('text-red-500');
          } else {
            icon.classList.add('text-red-500');
          }
        }
        showToast(inWishlist ? 'Removed from wishlist.' : 'Added to wishlist.', 'success');
      } catch (error) {
        showToast(error.message || 'Failed to update wishlist.', 'error');
      } finally {
        if (icon) {
          icon.classList.remove('fa-spinner', 'fa-spin');
        }
        btn.disabled = false;
      }
    });
  });

  syncCartPageEmptyState();
});
