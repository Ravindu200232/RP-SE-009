jest.mock('../models/inquiry.js', () => {
  const MockInquiry = jest.fn().mockImplementation((data) => ({
    ...data,
    _id: 'inq123',
    save: jest.fn().mockResolvedValue({ _id: 'inq123', ...data }),
  }));
  MockInquiry.find      = jest.fn();
  MockInquiry.findOne   = jest.fn();
  MockInquiry.updateOne = jest.fn();
  MockInquiry.deleteOne = jest.fn();
  return { __esModule: true, default: MockInquiry };
});

import Inquiry from '../models/inquiry.js';
import { addInquiry, getInquiry, deleteInquiry, updateInquiry } from '../controllers/InquiryController.js';

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

// ── addInquiry ────────────────────────────────────────────────────────────────
describe('addInquiry', () => {
  it('adds inquiry when user is logged in', async () => {
    const req = mockReq({
      body: { message: 'Where is my order?' },
      user: { email: 'c@c.com', phone: '0771234567' },
    });
    const res = mockRes();
    // Controller calls Inquiry.find().sort({id:-1}).limit(1) — mock the chain
    Inquiry.find.mockReturnValue({
      sort: jest.fn().mockReturnValue({ limit: jest.fn().mockResolvedValue([]) }),
    });

    await addInquiry(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Inquiry added successfully' });
  });

  it('returns 401 when user is not logged in', async () => {
    const req = mockReq({ body: { message: 'hello' }, user: null });
    const res = mockRes();

    await addInquiry(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
    expect(res.json).toHaveBeenCalledWith({ message: 'Please login and try again' });
  });
});

// ── getInquiry ────────────────────────────────────────────────────────────────
describe('getInquiry', () => {
  it('returns all inquiries for admin', async () => {
    const req = mockReq({ user: { role: 'admin' } });
    const res = mockRes();
    Inquiry.find.mockResolvedValue([{ message: 'test' }]);

    await getInquiry(req, res);

    expect(res.json).toHaveBeenCalledWith([{ message: 'test' }]);
  });

  it('returns only own inquiries for customer', async () => {
    const req = mockReq({ user: { role: 'customer', email: 'c@c.com' } });
    const res = mockRes();
    Inquiry.find.mockResolvedValue([{ email: 'c@c.com', message: 'my inquiry' }]);

    await getInquiry(req, res);

    expect(Inquiry.find).toHaveBeenCalledWith({ email: 'c@c.com' });
    expect(res.json).toHaveBeenCalledWith([{ email: 'c@c.com', message: 'my inquiry' }]);
  });

  it('returns unauthorized message for restaurant role', async () => {
    const req = mockReq({ user: { role: 'restaurant' } });
    const res = mockRes();

    await getInquiry(req, res);

    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'you are not authorized to perform this action' }),
    );
  });
});

// ── deleteInquiry ─────────────────────────────────────────────────────────────
describe('deleteInquiry', () => {
  it('admin can delete any inquiry', async () => {
    const req = mockReq({ params: { id: 'inq123' }, user: { role: 'admin' } });
    const res = mockRes();
    Inquiry.deleteOne.mockResolvedValue({ deletedCount: 1 });

    await deleteInquiry(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Inquiry deleted successfully' });
  });

  it('returns 403 for unauthorized roles', async () => {
    const req = mockReq({ params: { id: 'inq123' }, user: { role: 'restaurant' } });
    const res = mockRes();

    await deleteInquiry(req, res);

    expect(res.status).toHaveBeenCalledWith(403);
  });
});

// ── updateInquiry ─────────────────────────────────────────────────────────────
describe('updateInquiry', () => {
  it('admin can update any inquiry', async () => {
    const req = mockReq({
      params: { id: 'inq123' },
      body: { message: 'Updated message' },
      user: { role: 'admin' },
    });
    const res = mockRes();
    Inquiry.updateOne.mockResolvedValue({ modifiedCount: 1 });

    await updateInquiry(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Inquiry updated successfully' });
  });

  it('customer can update own inquiry', async () => {
    const req = mockReq({
      params: { id: 'inq123' },
      body: { message: 'My updated message' },
      user: { role: 'customer', email: 'c@c.com' },
    });
    const res = mockRes();
    Inquiry.findOne.mockResolvedValue({ _id: 'inq123', email: 'c@c.com' });
    Inquiry.updateOne.mockResolvedValue({ modifiedCount: 1 });

    await updateInquiry(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Inquiry update successfully' });
  });

  it('customer cannot update another customer\'s inquiry', async () => {
    const req = mockReq({
      params: { id: 'inq123' },
      body: { message: 'hacked' },
      user: { role: 'customer', email: 'attacker@e.com' },
    });
    const res = mockRes();
    Inquiry.findOne.mockResolvedValue({ _id: 'inq123', email: 'owner@e.com' });

    await updateInquiry(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});
