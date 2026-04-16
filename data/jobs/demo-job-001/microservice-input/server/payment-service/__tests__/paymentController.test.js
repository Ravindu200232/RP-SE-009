jest.mock('../models/payment.js', () => {
  const MockPayment = jest.fn().mockImplementation((data) => ({
    ...data,
    _id: 'pay123',
    save: jest.fn().mockResolvedValue({ _id: 'pay123', ...data }),
  }));
  MockPayment.find = jest.fn();
  return { __esModule: true, default: MockPayment };
});

jest.mock('bcrypt', () => ({
  hash: jest.fn().mockResolvedValue('hashedvalue'),
}));

jest.mock('axios', () => ({
  put: jest.fn().mockResolvedValue({ data: {} }),
}));

import Payment from '../models/payment.js';
import bcrypt  from 'bcrypt';
import axios   from 'axios';
import { makePayment, getAllPayments } from '../controllers/paymentController.js';

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

// ── makePayment ───────────────────────────────────────────────────────────────
describe('makePayment', () => {
  const validBody = {
    bookingId:   'ORD0001',
    amount:      1650,
    paymentType: 'Card',
    cardNumber:  '4111111111111111',
    expiry:      '12/26',
    cvv:         '123',
  };

  it('processes payment successfully and notifies order service', async () => {
    const req = mockReq({ body: validBody, user: { role: 'customer' } });
    const res = mockRes();

    await makePayment(req, res);

    expect(bcrypt.hash).toHaveBeenCalledTimes(3); // cardNumber, expiry, cvv
    expect(res.status).toHaveBeenCalledWith(200);
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Payment successful' }),
    );
  });

  it('calls order service to update payment status to paid', async () => {
    const req = mockReq({ body: validBody, user: { role: 'customer' } });
    const res = mockRes();

    await makePayment(req, res);

    expect(axios.put).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/orders/status/ORD0001'),
      { paymentStatus: 'paid', status: 'confirmed' },
    );
  });

  it('still succeeds if order service call fails (non-critical)', async () => {
    axios.put.mockRejectedValueOnce(new Error('Order service down'));
    const req = mockReq({ body: validBody, user: { role: 'customer' } });
    const res = mockRes();

    await makePayment(req, res);

    expect(res.status).toHaveBeenCalledWith(200);
  });

  it('returns 500 on payment save failure', async () => {
    Payment.mockImplementationOnce(() => ({
      save: jest.fn().mockRejectedValue(new Error('DB error')),
    }));
    const req = mockReq({ body: validBody });
    const res = mockRes();

    await makePayment(req, res);

    expect(res.status).toHaveBeenCalledWith(500);
    expect(res.json).toHaveBeenCalledWith({ message: 'Payment processing error' });
  });
});

// ── getAllPayments ─────────────────────────────────────────────────────────────
describe('getAllPayments', () => {
  it('admin can retrieve all payments (sensitive fields excluded)', async () => {
    const payments = [{ bookingId: 'ORD0001', amount: 1650, paymentType: 'Card' }];
    const mockSelect = jest.fn().mockResolvedValue(payments);
    Payment.find.mockReturnValue({ select: mockSelect });

    const req = mockReq({ user: { role: 'admin' } });
    const res = mockRes();

    await getAllPayments(req, res);

    expect(mockSelect).toHaveBeenCalledWith('-cardNumber -expiry -cvv');
    expect(res.status).toHaveBeenCalledWith(200);
    expect(res.json).toHaveBeenCalledWith(payments);
  });

  it('returns 403 for non-admin users', async () => {
    const req = mockReq({ user: { role: 'customer' } });
    const res = mockRes();

    await getAllPayments(req, res);

    expect(res.status).toHaveBeenCalledWith(403);
    expect(res.json).toHaveBeenCalledWith({ message: 'Access denied. Admins only.' });
  });

  it('returns 403 when not logged in', async () => {
    const req = mockReq({ user: null });
    const res = mockRes();

    await getAllPayments(req, res);

    expect(res.status).toHaveBeenCalledWith(403);
  });

  it('returns 500 on database error', async () => {
    Payment.find.mockReturnValue({ select: jest.fn().mockRejectedValue(new Error('DB error')) });
    const req = mockReq({ user: { role: 'admin' } });
    const res = mockRes();

    await getAllPayments(req, res);

    expect(res.status).toHaveBeenCalledWith(500);
  });
});
