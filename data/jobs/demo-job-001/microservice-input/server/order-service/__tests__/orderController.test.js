jest.mock('../models/collection.js', () => {
  const MockCollection = jest.fn();
  MockCollection.findById = jest.fn();
  MockCollection.findOne  = jest.fn();
  return { __esModule: true, default: MockCollection };
});

jest.mock('../models/order.js', () => {
  const MockOrder = jest.fn().mockImplementation((data) => ({
    ...data,
    _id: 'order123',
    save: jest.fn().mockResolvedValue({ _id: 'order123', orderId: 'ORD0001', ...data }),
  }));
  MockOrder.find            = jest.fn();
  MockOrder.findOne         = jest.fn();
  MockOrder.findOneAndUpdate = jest.fn();
  MockOrder.updateOne       = jest.fn();
  MockOrder.deleteOne       = jest.fn();
  return { __esModule: true, default: MockOrder };
});

jest.mock('axios', () => ({ get: jest.fn(), put: jest.fn().mockResolvedValue({ data: {} }) }));

import Collection from '../models/collection.js';
import Order      from '../models/order.js';
import {
  addOrder, getOrder, deleteOrder, getQuote, updateStatus, isApprove,
} from '../controllers/orderController.js';

const mockReq = (overrides = {}) => ({
  body: {}, params: {}, user: null, ...overrides,
});
const mockRes = () => {
  const res = {};
  res.status = jest.fn().mockReturnValue(res);
  res.json   = jest.fn().mockReturnValue(res);
  return res;
};

beforeEach(() => jest.clearAllMocks());

// ── addOrder ──────────────────────────────────────────────────────────────────
describe('addOrder', () => {
  const product = {
    _id: 'prod1', name: 'Burger', price: 500,
    available: true, restaurantId: 'r1', ownerId: 'o1',
    images: ['img.jpg'],
  };
  const userPayload = {
    id: 'u1', email: 'c@c.com', address: '123 St',
    firstName: 'John', lastName: 'Doe', phone: '0771234567',
    lat: 6.9, lng: 79.8,
  };

  it('creates an order successfully', async () => {
    const req = mockReq({
      body: { orderItem: [{ key: 'prod1', qty: 2 }] },
      user: userPayload,
    });
    const res = mockRes();
    Collection.findById.mockResolvedValue(product);
    // Controller calls Order.find().sort({ orderId: -1 }).limit(1) — mock the chain
    Order.find.mockReturnValue({
      sort: jest.fn().mockReturnValue({ limit: jest.fn().mockResolvedValue([{ orderId: 'ORD0000' }]) }),
    });

    await addOrder(req, res);

    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Orders created successfully' }),
    );
  });

  it('returns 401 when user is not logged in', async () => {
    const req = mockReq({ body: { orderItem: [{ key: 'p1', qty: 1 }] }, user: null });
    const res = mockRes();

    await addOrder(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
    expect(res.json).toHaveBeenCalledWith({ message: 'Please login and try again' });
  });

  it('returns 404 when product does not exist', async () => {
    const req = mockReq({ body: { orderItem: [{ key: 'nonexistent', qty: 1 }] }, user: userPayload });
    const res = mockRes();
    Collection.findById.mockResolvedValue(null);

    await addOrder(req, res);

    expect(res.status).toHaveBeenCalledWith(404);
  });

  it('returns 400 when product is not available', async () => {
    const req = mockReq({ body: { orderItem: [{ key: 'prod1', qty: 1 }] }, user: userPayload });
    const res = mockRes();
    Collection.findById.mockResolvedValue({ ...product, available: false });

    await addOrder(req, res);

    expect(res.status).toHaveBeenCalledWith(400);
  });
});

// ── getOrder ──────────────────────────────────────────────────────────────────
describe('getOrder', () => {
  it('returns all orders for admin', async () => {
    const req = mockReq({ user: { role: 'admin' } });
    const res = mockRes();
    Order.find.mockResolvedValue([{ orderId: 'ORD0001' }]);

    await getOrder(req, res);

    expect(res.json).toHaveBeenCalledWith([{ orderId: 'ORD0001' }]);
  });

  it('returns restaurant-specific orders for restaurant role', async () => {
    const req = mockReq({ user: { role: 'restaurant', id: 'owner1' } });
    const res = mockRes();
    Order.find.mockResolvedValue([{ orderId: 'ORD0002', ownerId: 'owner1' }]);

    await getOrder(req, res);

    expect(Order.find).toHaveBeenCalledWith({ ownerId: 'owner1' });
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ user: null });
    const res = mockRes();

    await getOrder(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});

// ── getQuote ──────────────────────────────────────────────────────────────────
describe('getQuote', () => {
  const product = {
    _id: 'prod1', name: 'Pizza', price: 800,
    available: true, images: ['img.jpg'], restaurantId: 'r1',
  };

  it('returns correct quote for given items', async () => {
    const req = mockReq({ body: { orderItem: [{ key: 'prod1', qty: 3 }] } });
    const res = mockRes();
    Collection.findOne.mockResolvedValue(product);

    await getQuote(req, res);

    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Order quotation', total: 2400 }),
    );
  });

  it('returns 404 when product not found', async () => {
    const req = mockReq({ body: { orderItem: [{ key: 'bad', qty: 1 }] } });
    const res = mockRes();
    Collection.findOne.mockResolvedValue(null);

    await getQuote(req, res);

    expect(res.status).toHaveBeenCalledWith(404);
  });

  it('returns 400 when product is not available', async () => {
    const req = mockReq({ body: { orderItem: [{ key: 'prod1', qty: 1 }] } });
    const res = mockRes();
    Collection.findOne.mockResolvedValue({ ...product, available: false });

    await getQuote(req, res);

    expect(res.status).toHaveBeenCalledWith(400);
  });
});

// ── updateStatus ──────────────────────────────────────────────────────────────
describe('updateStatus', () => {
  it('updates order status successfully', async () => {
    const updatedOrder = { orderId: 'ORD0001', status: 'confirmed' };
    const req = mockReq({ params: { id: 'ORD0001' }, body: { status: 'confirmed' } });
    const res = mockRes();
    Order.findOneAndUpdate.mockResolvedValue(updatedOrder);

    await updateStatus(req, res);

    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Status updated successfully' }),
    );
  });

  it('returns 404 when order not found', async () => {
    const req = mockReq({ params: { id: 'ORDX' }, body: { status: 'confirmed' } });
    const res = mockRes();
    Order.findOneAndUpdate.mockResolvedValue(null);

    await updateStatus(req, res);

    expect(res.status).toHaveBeenCalledWith(404);
    expect(res.json).toHaveBeenCalledWith({ message: 'Order not found' });
  });
});

// ── isApprove ─────────────────────────────────────────────────────────────────
describe('isApprove', () => {
  it('approves order for admin', async () => {
    const req = mockReq({ params: { id: 'order123' }, user: { role: 'admin' } });
    const res = mockRes();
    Order.updateOne.mockResolvedValue({ modifiedCount: 1 });

    await isApprove(req, res);

    expect(res.json).toHaveBeenCalledWith('Order Approved');
  });

  it('returns 401 for non-admin', async () => {
    const req = mockReq({ params: { id: 'order123' }, user: { role: 'customer' } });
    const res = mockRes();

    await isApprove(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ params: { id: 'order123' }, user: null });
    const res = mockRes();

    await isApprove(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});
