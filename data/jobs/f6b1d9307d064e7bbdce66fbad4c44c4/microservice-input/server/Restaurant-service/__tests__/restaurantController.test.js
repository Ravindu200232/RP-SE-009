jest.mock('../models/resturants.js', () => {
  const MockRestaurant = jest.fn().mockImplementation((data) => ({
    ...data,
    _id: 'rest123',
    save: jest.fn().mockResolvedValue({ _id: 'rest123', ...data }),
  }));
  MockRestaurant.find      = jest.fn();
  MockRestaurant.findOne   = jest.fn();
  MockRestaurant.updateOne = jest.fn();
  MockRestaurant.deleteOne = jest.fn();
  return { __esModule: true, default: MockRestaurant };
});

import Restaurant from '../models/resturants.js';
import {
  createRestaurant, getRestaurant, updateRestaurant,
  deleteRestaurant, isOpen, closeShop, verification, getOne,
} from '../controllers/resturantsController.js';

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

// ── createRestaurant ──────────────────────────────────────────────────────────
describe('createRestaurant', () => {
  it('creates a restaurant for restaurant role', async () => {
    const req = mockReq({
      body: { name: 'Spice Garden', address: 'Colombo', phone: '0112345678' },
      user: { id: 'u1', role: 'restaurant', firstName: 'Ravi', lastName: 'K' },
    });
    const res = mockRes();

    await createRestaurant(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Restaurant added successfully' });
  });

  it('returns 401 for customer role', async () => {
    const req = mockReq({
      body: { name: 'test' },
      user: { id: 'u1', role: 'customer' },
    });
    const res = mockRes();

    await createRestaurant(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ body: { name: 'test' }, user: null });
    const res = mockRes();

    await createRestaurant(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});

// ── getRestaurant ─────────────────────────────────────────────────────────────
describe('getRestaurant', () => {
  it('admin gets all restaurants', async () => {
    const req = mockReq({ user: { role: 'admin' } });
    const res = mockRes();
    Restaurant.find.mockResolvedValue([{ name: 'R1' }, { name: 'R2' }]);

    await getRestaurant(req, res);

    expect(res.json).toHaveBeenCalledWith([{ name: 'R1' }, { name: 'R2' }]);
  });

  it('customer sees only verified restaurants', async () => {
    const req = mockReq({ user: { role: 'customer' } });
    const res = mockRes();
    Restaurant.find.mockResolvedValue([{ name: 'Verified R', verified: true }]);

    await getRestaurant(req, res);

    expect(Restaurant.find).toHaveBeenCalledWith({ verified: true });
  });

  it('restaurant owner sees only own restaurants', async () => {
    const req = mockReq({ user: { role: 'restaurant', id: 'owner1' } });
    const res = mockRes();
    Restaurant.find.mockResolvedValue([{ name: 'My R', ownerId: 'owner1' }]);

    await getRestaurant(req, res);

    expect(Restaurant.find).toHaveBeenCalledWith({ ownerId: 'owner1' });
  });

  it('unauthenticated user sees only verified restaurants', async () => {
    const req = mockReq({ user: null });
    const res = mockRes();
    Restaurant.find.mockResolvedValue([{ name: 'Open R', verified: true }]);

    await getRestaurant(req, res);

    expect(Restaurant.find).toHaveBeenCalledWith({ verified: true });
  });
});

// ── deleteRestaurant ──────────────────────────────────────────────────────────
describe('deleteRestaurant', () => {
  it('admin can delete any restaurant', async () => {
    const req = mockReq({ params: { id: 'rest123' }, user: { role: 'admin' } });
    const res = mockRes();
    Restaurant.deleteOne.mockResolvedValue({ deletedCount: 1 });

    await deleteRestaurant(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Restaurant Delete Successfully' });
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ params: { id: 'rest123' }, user: null });
    const res = mockRes();

    await deleteRestaurant(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});

// ── isOpen ────────────────────────────────────────────────────────────────────
describe('isOpen', () => {
  it('admin can mark restaurant as open', async () => {
    const req = mockReq({ params: { id: 'rest123' }, user: { role: 'admin' } });
    const res = mockRes();
    Restaurant.updateOne.mockResolvedValue({ modifiedCount: 1 });

    await isOpen(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Shop informing Shop is Open now' });
  });

  it('restaurant owner can mark own restaurant as open', async () => {
    const req = mockReq({ params: { id: 'rest123' }, user: { role: 'restaurant', id: 'owner1' } });
    const res = mockRes();
    Restaurant.updateOne.mockResolvedValue({ modifiedCount: 1 });

    await isOpen(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Shop informing Shop is Open now' });
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ params: { id: 'rest123' }, user: null });
    const res = mockRes();

    await isOpen(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});

// ── closeShop ─────────────────────────────────────────────────────────────────
describe('closeShop', () => {
  it('admin can close a restaurant', async () => {
    const req = mockReq({ params: { id: 'rest123' }, user: { role: 'admin' } });
    const res = mockRes();
    Restaurant.updateOne.mockResolvedValue({ modifiedCount: 1 });

    await closeShop(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Shop is now closed.' });
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ params: { id: 'rest123' }, user: null });
    const res = mockRes();

    await closeShop(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});

// ── verification ──────────────────────────────────────────────────────────────
describe('verification', () => {
  it('admin can verify a restaurant', async () => {
    const req = mockReq({ params: { id: 'rest123' }, user: { role: 'admin' } });
    const res = mockRes();
    Restaurant.updateOne.mockResolvedValue({ modifiedCount: 1 });

    await verification(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Restaurant verification Successfully' });
  });

  it('non-admin cannot verify a restaurant', async () => {
    const req = mockReq({ params: { id: 'rest123' }, user: { role: 'restaurant' } });
    const res = mockRes();

    await verification(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ params: { id: 'rest123' }, user: null });
    const res = mockRes();

    await verification(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});

// ── getOne ────────────────────────────────────────────────────────────────────
describe('getOne', () => {
  it('returns a single restaurant by id', async () => {
    const restaurant = { _id: 'rest123', name: 'Spice Garden' };
    const req = mockReq({ params: { id: 'rest123' } });
    const res = mockRes();
    Restaurant.findOne.mockResolvedValue(restaurant);

    await getOne(req, res);

    expect(res.json).toHaveBeenCalledWith(restaurant);
  });

  it('returns 500 on database error', async () => {
    const req = mockReq({ params: { id: 'rest123' } });
    const res = mockRes();
    Restaurant.findOne.mockRejectedValue(new Error('DB error'));

    await getOne(req, res);

    expect(res.status).toHaveBeenCalledWith(500);
  });
});
