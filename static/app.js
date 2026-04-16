const state = {
  statuses: [],
  priceCatalog: {},
};

const statusClassMap = {
  RECEIVED: "status-received",
  PROCESSING: "status-processing",
  READY: "status-ready",
  DELIVERED: "status-delivered",
};

const orderForm = document.querySelector("#order-form");
const orderItemsContainer = document.querySelector("#order-items");
const orderTotalPreview = document.querySelector("#order-total-preview");
const ordersTableBody = document.querySelector("#orders-table-body");
const filtersForm = document.querySelector("#filters-form");
const toast = document.querySelector("#toast");

function formatCurrency(amount) {
  return `Rs ${Number(amount || 0).toFixed(2)}`;
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    toast.hidden = true;
  }, 2800);
}

function getNextStatus(status) {
  const currentIndex = state.statuses.indexOf(status);
  if (currentIndex === -1 || currentIndex === state.statuses.length - 1) {
    return null;
  }
  return state.statuses[currentIndex + 1];
}

async function updateOrderStatus(orderId, status, successMessage) {
  await fetchJson(`/api/orders/${orderId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
  showToast(successMessage);
  await Promise.all([loadDashboard(), loadOrders()]);
}

function createStatusOptions(options, selectedValue = "") {
  return options
    .map((status) => `<option value="${status}" ${status === selectedValue ? "selected" : ""}>${status}</option>`)
    .join("");
}

function createGarmentOptions() {
  return Object.entries(state.priceCatalog)
    .map(([garment, price]) => `<option value="${garment}" data-price="${price}">${garment} - ${formatCurrency(price)}</option>`)
    .join("");
}

function calculateOrderPreview() {
  const rows = Array.from(orderItemsContainer.querySelectorAll(".item-row"));
  const total = rows.reduce((sum, row) => {
    const quantity = Number(row.querySelector(".item-quantity").value || 0);
    const unitPrice = Number(row.querySelector(".item-price").value || 0);
    return sum + quantity * unitPrice;
  }, 0);

  orderTotalPreview.textContent = formatCurrency(total);
}

function addItemRow(defaults = {}) {
  const row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML = `
    <label>
      Garment Type
      <select class="item-garment">
        ${createGarmentOptions()}
      </select>
    </label>
    <label>
      Quantity
      <input class="item-quantity" type="number" min="1" value="${defaults.quantity || 1}">
    </label>
    <label>
      Unit Price
      <input class="item-price" type="number" min="1" step="0.01" value="${defaults.unit_price || ""}" readonly>
    </label>
    <button class="danger-button remove-item" type="button">Remove</button>
  `;

  const garmentSelect = row.querySelector(".item-garment");
  const priceInput = row.querySelector(".item-price");
  const syncCatalogPrice = () => {
    const catalogPrice = state.priceCatalog[garmentSelect.value];
    priceInput.value = Number(catalogPrice || 0).toFixed(2);
    calculateOrderPreview();
  };

  garmentSelect.value = defaults.garment_type || Object.keys(state.priceCatalog)[0] || "";
  syncCatalogPrice();

  garmentSelect.addEventListener("change", () => {
    syncCatalogPrice();
  });

  row.querySelector(".item-quantity").addEventListener("input", calculateOrderPreview);
  row.querySelector(".remove-item").addEventListener("click", () => {
    row.remove();
    if (!orderItemsContainer.children.length) {
      addItemRow();
    }
    calculateOrderPreview();
  });

  orderItemsContainer.appendChild(row);
  calculateOrderPreview();
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Something went wrong.");
  }

  return data;
}

async function loadConfig() {
  const config = await fetchJson("/api/config");
  state.statuses = config.statuses;
  state.priceCatalog = config.price_catalog;

  document.querySelector("#status-pill-list").innerHTML = state.statuses
    .map((status) => `<span class="pill">${status}</span>`)
    .join("");

  const filterStatus = document.querySelector("#filter-status");
  filterStatus.innerHTML = `<option value="">All</option>${createStatusOptions(state.statuses)}`;

  if (!orderItemsContainer.children.length) {
    addItemRow();
  }
}

async function loadDashboard() {
  const dashboard = await fetchJson("/api/dashboard");
  document.querySelector("#metric-total-orders").textContent = dashboard.total_orders;
  document.querySelector("#metric-total-revenue").textContent = formatCurrency(dashboard.total_revenue);
  document.querySelector("#metric-received").textContent = dashboard.orders_per_status.RECEIVED;
  document.querySelector("#metric-processing").textContent = dashboard.orders_per_status.PROCESSING;
  document.querySelector("#metric-ready").textContent = dashboard.orders_per_status.READY;
  document.querySelector("#metric-delivered").textContent = dashboard.orders_per_status.DELIVERED;
}

function renderOrders(orders) {
  if (!orders.length) {
    ordersTableBody.innerHTML = `
      <tr>
        <td colspan="8" class="empty-state">No matching orders found.</td>
      </tr>
    `;
    return;
  }

  ordersTableBody.innerHTML = orders
    .map(
      (order) => `
        <tr>
          <td>
            <strong>${order.order_id}</strong><br>
            <span class="garment-line">${new Date(order.created_at).toLocaleString()}</span>
          </td>
          <td>
            <strong>${order.customer_name}</strong><br>
            <span class="garment-line">${order.phone}</span>
          </td>
          <td>
            <div class="garment-stack">
              ${order.items
                .map(
                  (item) => `
                    <span class="garment-line">
                      ${item.garment_type} x ${item.quantity} @ ${formatCurrency(item.unit_price)}
                    </span>
                  `
                )
                .join("")}
            </div>
          </td>
          <td><strong>${order.total_items}</strong></td>
          <td><strong>${formatCurrency(order.total_amount)}</strong></td>
          <td>${order.estimated_delivery}</td>
          <td>
            <span class="status-badge ${statusClassMap[order.status] || ""}">${order.status}</span>
          </td>
          <td>
            <div class="row-actions">
              ${
                getNextStatus(order.status)
                  ? `<button class="secondary-button js-advance-status" type="button" data-order-id="${order.order_id}" data-next-status="${getNextStatus(order.status)}">
                      Move to ${getNextStatus(order.status)}
                    </button>`
                  : ""
              }
              ${
                order.status !== "DELIVERED"
                  ? `<button class="primary-button js-mark-delivered" type="button" data-order-id="${order.order_id}">
                      Mark as Delivered
                    </button>`
                  : ""
              }
            </div>
          </td>
        </tr>
      `
    )
    .join("");

  Array.from(document.querySelectorAll(".js-advance-status")).forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await updateOrderStatus(
          button.dataset.orderId,
          button.dataset.nextStatus,
          `Order ${button.dataset.orderId} moved to ${button.dataset.nextStatus}.`
        );
      } catch (error) {
        showToast(error.message);
      }
    });
  });

  Array.from(document.querySelectorAll(".js-mark-delivered")).forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await updateOrderStatus(
          button.dataset.orderId,
          "DELIVERED",
          `Order ${button.dataset.orderId} marked as delivered.`
        );
      } catch (error) {
        showToast(error.message);
      }
    });
  });
}

async function loadOrders() {
  const formData = new FormData(filtersForm);
  const params = new URLSearchParams();

  formData.forEach((value, key) => {
    if (String(value).trim()) {
      params.set(key, value);
    }
  });

  const queryString = params.toString();
  const url = queryString ? `/api/orders?${queryString}` : "/api/orders";
  const data = await fetchJson(url);
  renderOrders(data.orders);
}

orderForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(orderForm);
  const items = Array.from(orderItemsContainer.querySelectorAll(".item-row")).map((row) => ({
    garment_type: row.querySelector(".item-garment").value,
    quantity: Number(row.querySelector(".item-quantity").value),
    unit_price: Number(row.querySelector(".item-price").value),
  }));

  const payload = {
    customer_name: formData.get("customer_name"),
    phone: formData.get("phone"),
    estimated_delivery: formData.get("estimated_delivery"),
    items,
  };

  try {
    const order = await fetchJson("/api/orders", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    orderForm.reset();
    orderItemsContainer.innerHTML = "";
    addItemRow();
    orderForm.elements.estimated_delivery.value = new Date(Date.now() + 2 * 86400000)
      .toISOString()
      .split("T")[0];
    showToast(`Order ${order.order_id} created for ${order.customer_name}.`);
    await Promise.all([loadDashboard(), loadOrders()]);
  } catch (error) {
    showToast(error.message);
  }
});

filtersForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await loadOrders();
});

document.querySelector("#refresh-dashboard").addEventListener("click", async () => {
  await Promise.all([loadDashboard(), loadOrders()]);
  showToast("Dashboard refreshed.");
});

document.querySelector("#reset-filters").addEventListener("click", async () => {
  filtersForm.reset();
  await loadOrders();
});

document.querySelector("#add-item").addEventListener("click", () => addItemRow());

async function initialize() {
  const etaInput = orderForm.elements.estimated_delivery;
  etaInput.value = new Date(Date.now() + 2 * 86400000).toISOString().split("T")[0];

  try {
    await loadConfig();
    await Promise.all([loadDashboard(), loadOrders()]);
  } catch (error) {
    showToast(error.message);
  }
}

initialize();
