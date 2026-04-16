jest.mock('../models/delivery.js', () => {
  const MockDelivery = jest.fn().mockImplementation((data) => ({
    ...data,
    _id: 'del123',
    save: jest.fn().mockResolvedValue({ _id: 'del123', ...data }),
  }));
  MockDelivery.find            = jest.fn();
  MockDelivery.findOne         = jest.fn();
  MockDelivery.findByIdAndUpdate = jest.fn();
  return { __esModule: true, default: MockDelivery };
});

jest.mock('axios', () => ({
  put: jest.fn().mockResolvedValue({ data: {} }),
}));

import Delivery from '../models/delivery.js';
import {
  addDelivery, getDelivery, updateDeliveryLocation,
  updateDeliveryStatus, getLocation,
} from '../controllers/deliverController.js';

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

// ── addDelivery ───────────────────────────────────────────────────────────────
describe('addDelivery', () => {
  it('adds a new delivery record', async () => {
    const req = mockReq({
      body: {
        driverId: 'd1', driverName: 'Kamal', customerEmail: 'c@c.com',
        orderId: 'ORD0001', address: '123 St', lat: 6.9, lng: 79.8,
      },
      user: { role: 'admin' },
    });
    const res = mockRes();

    await addDelivery(req, res);

    expect(res.json).toHaveBeenCalledWith('Delivery details added successfully');
  });

  it('returns 500 on save error', async () => {
    const MockDeliveryInstance = { save: jest.fn().mockRejectedValue(new Error('DB error')) };
    Delivery.mockImplementationOnce(() => MockDeliveryInstance);

    const req = mockReq({ body: { driverId: 'd1' }, user: { role: 'admin' } });
    const res = mockRes();

    await addDelivery(req, res);

    expect(res.status).toHaveBeenCalledWith(500);
  });
});

// ── getDelivery ───────────────────────────────────────────────────────────────
describe('getDelivery', () => {
  it('customer sees own deliveries', async () => {
    const req = mockReq({ user: { role: 'customer', email: 'c@c.com', id: 'u1' } });
    const res = mockRes();
    Delivery.find.mockResolvedValue([{ customerEmail: 'c@c.com' }]);

    await getDelivery(req, res);

    expect(Delivery.find).toHaveBeenCalledWith({ customerEmail: 'c@c.com' });
  });

  it('driver sees own deliveries', async () => {
    const req = mockReq({ user: { role: 'delivery', id: 'driver1', email: 'd@d.com' } });
    const res = mockRes();
    Delivery.find.mockResolvedValue([{ driverId: 'driver1' }]);

    await getDelivery(req, res);

    expect(Delivery.find).toHaveBeenCalledWith({ driverId: 'driver1' });
  });
});

// ── updateDeliveryLocation ────────────────────────────────────────────────────
describe('updateDeliveryLocation', () => {
  it('updates location with valid lat/lng', async () => {
    const updated = { _id: 'del123', lat: 6.95, lng: 79.85 };
    const req = mockReq({ params: { id: 'del123' }, body: { lat: 6.95, lng: 79.85 } });
    const res = mockRes();
    Delivery.findByIdAndUpdate.mockResolvedValue(updated);

    await updateDeliveryLocation(req, res);

    expect(res.json).toHaveBeenCalledWith(updated);
  });

  it('returns 400 when lat or lng is missing', async () => {
    const req = mockReq({ params: { id: 'del123' }, body: { lat: 6.95 } });
    const res = mockRes();

    await updateDeliveryLocation(req, res);

    expect(res.status).toHaveBeenCalledWith(400);
    expect(res.json).toHaveBeenCalledWith({ error: 'Latitude and longitude are required' });
  });

  it('returns 404 when delivery not found', async () => {
    const req = mockReq({ params: { id: 'noexist' }, body: { lat: 6.9, lng: 79.8 } });
    const res = mockRes();
    Delivery.findByIdAndUpdate.mockResolvedValue(null);

    await updateDeliveryLocation(req, res);

    expect(res.status).toHaveBeenCalledWith(404);
    expect(res.json).toHaveBeenCalledWith({ error: 'Delivery not found' });
  });
});

// ── updateDeliveryStatus ──────────────────────────────────────────────────────
describe('updateDeliveryStatus', () => {
  it('updates status successfully and syncs with order service', async () => {
    const updated = { _id: 'del123', status: 'on the way', orderId: 'ORD0001' };
    const req = mockReq({ params: { id: 'del123' }, body: { status: 'on the way' } });
    const res = mockRes();
    Delivery.findByIdAndUpdate.mockResolvedValue(updated);

    await updateDeliveryStatus(req, res);

    expect(res.json).toHaveBeenCalledWith(updated);
  });

  it('returns 400 when status is missing', async () => {
    const req = mockReq({ params: { id: 'del123' }, body: {} });
    const res = mockRes();

    await updateDeliveryStatus(req, res);

    expect(res.status).toHaveBeenCalledWith(400);
    expect(res.json).toHaveBeenCalledWith({ error: 'Status is required' });
  });

  it('returns 404 when delivery not found', async () => {
    const req = mockReq({ params: { id: 'noexist' }, body: { status: 'delivered' } });
    const res = mockRes();
    Delivery.findByIdAndUpdate.mockResolvedValue(null);

    await updateDeliveryStatus(req, res);

    expect(res.status).toHaveBeenCalledWith(404);
  });
});

// ── getLocation ───────────────────────────────────────────────────────────────
describe('getLocation', () => {
  it('returns delivery location by id', async () => {
    const delivery = { _id: 'del123', lat: 6.9, lng: 79.8 };
    const req = mockReq({ params: { id: 'del123' } });
    const res = mockRes();
    Delivery.findOne.mockResolvedValue(delivery);

    await getLocation(req, res);

    expect(res.json).toHaveBeenCalledWith(delivery);
  });

  it('returns 500 on database error', async () => {
    const req = mockReq({ params: { id: 'del123' } });
    const res = mockRes();
    Delivery.findOne.mockRejectedValue(new Error('DB error'));

    await getLocation(req, res);

    expect(res.status).toHaveBeenCalledWith(500);
  });
});
