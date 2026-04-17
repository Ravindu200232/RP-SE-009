jest.mock('../models/driver.js', () => {
  const MockDriver = jest.fn().mockImplementation((data) => ({
    ...data,
    _id: 'driver123',
    save: jest.fn().mockResolvedValue({ _id: 'driver123', ...data }),
  }));
  MockDriver.findOne   = jest.fn();
  MockDriver.find      = jest.fn();
  MockDriver.updateOne = jest.fn();
  MockDriver.deleteOne = jest.fn();
  return { __esModule: true, default: MockDriver };
});

jest.mock('bcrypt', () => ({
  hashSync:    jest.fn().mockReturnValue('hashedpassword'),
  compareSync: jest.fn(),
}));

jest.mock('jsonwebtoken', () => ({
  sign: jest.fn().mockReturnValue('driver.jwt.token'),
}));

import Driver from '../models/driver.js';
import bcrypt from 'bcrypt';
import {
  createDriver, driverLogin, getDriver, updateDriver, deleteDriver,
} from '../controllers/driverController.js';

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

// ── createDriver ──────────────────────────────────────────────────────────────
describe('createDriver', () => {
  it('registers a new driver successfully', async () => {
    const req = mockReq({
      body: { name: 'Kamal', email: 'kamal@d.com', password: 'pass123', phone: '0771234567' },
    });
    const res = mockRes();
    Driver.findOne.mockResolvedValue(null);

    await createDriver(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Driver Added!' });
  });

  it('returns message when email already in use', async () => {
    const req = mockReq({ body: { email: 'taken@d.com', password: 'pass' } });
    const res = mockRes();
    Driver.findOne.mockResolvedValue({ email: 'taken@d.com' });

    await createDriver(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Email is Already use' });
  });

  it('returns 500 on database error', async () => {
    const req = mockReq({ body: { email: 'err@d.com', password: 'pass' } });
    const res = mockRes();
    Driver.findOne.mockRejectedValue(new Error('DB error'));

    await createDriver(req, res);

    expect(res.status).toHaveBeenCalledWith(500);
  });
});

// ── driverLogin ───────────────────────────────────────────────────────────────
describe('driverLogin', () => {
  const mockDriver = {
    _id: 'driver1', email: 'kamal@d.com',
    password: 'hashed', role: 'delivery', firstName: 'Kamal',
  };

  it('logs in driver with correct credentials', async () => {
    const req = mockReq({ body: { email: 'kamal@d.com', password: 'pass123' } });
    const res = mockRes();
    Driver.findOne.mockResolvedValue(mockDriver);
    bcrypt.compareSync.mockReturnValue(true);

    await driverLogin(req, res);

    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Login successfully', token: 'driver.jwt.token' }),
    );
  });

  it('returns message for wrong password', async () => {
    const req = mockReq({ body: { email: 'kamal@d.com', password: 'wrongpass' } });
    const res = mockRes();
    Driver.findOne.mockResolvedValue(mockDriver);
    bcrypt.compareSync.mockReturnValue(false);

    await driverLogin(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Password incorrect ,please try again!' });
  });

  it('returns 404 when driver not found', async () => {
    const req = mockReq({ body: { email: 'ghost@d.com', password: 'pass' } });
    const res = mockRes();
    Driver.findOne.mockResolvedValue(null);

    await driverLogin(req, res);

    expect(res.status).toHaveBeenCalledWith(404);
    expect(res.json).toHaveBeenCalledWith({ message: 'driver not found please try again!' });
  });
});

// ── getDriver ─────────────────────────────────────────────────────────────────
describe('getDriver', () => {
  it('admin gets all drivers', async () => {
    const req = mockReq({ user: { role: 'admin' } });
    const res = mockRes();
    Driver.find.mockResolvedValue([{ name: 'Kamal' }]);

    await getDriver(req, res);

    expect(res.json).toHaveBeenCalledWith([{ name: 'Kamal' }]);
  });

  it('restaurant sees only available drivers', async () => {
    const req = mockReq({ user: { role: 'restaurant' } });
    const res = mockRes();
    Driver.find.mockResolvedValue([{ name: 'Perera', isAvailable: true }]);

    await getDriver(req, res);

    expect(Driver.find).toHaveBeenCalledWith({ isAvailable: true });
  });

  it('delivery driver sees own profile', async () => {
    const req = mockReq({ user: { role: 'delivery', id: 'driver1' } });
    const res = mockRes();
    Driver.findOne.mockResolvedValue({ _id: 'driver1', name: 'Kamal' });

    await getDriver(req, res);

    expect(Driver.findOne).toHaveBeenCalledWith({ _id: 'driver1' });
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ user: null });
    const res = mockRes();

    await getDriver(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});

// ── updateDriver ──────────────────────────────────────────────────────────────
describe('updateDriver', () => {
  it('admin can update any driver', async () => {
    const req = mockReq({
      params: { id: 'driver1' }, body: { name: 'Updated' },
      user: { role: 'admin' },
    });
    const res = mockRes();
    Driver.updateOne.mockResolvedValue({ modifiedCount: 1 });

    await updateDriver(req, res);

    expect(res.json).toHaveBeenCalledWith('Driver update successfully');
  });

  it('delivery driver can update own profile', async () => {
    const req = mockReq({
      params: { id: 'driver1' }, body: { phone: '0779876543' },
      user: { role: 'delivery', id: 'driver1' },
    });
    const res = mockRes();
    Driver.updateOne.mockResolvedValue({ modifiedCount: 1 });

    await updateDriver(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'Driver update successfully' });
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ params: { id: 'driver1' }, body: {}, user: null });
    const res = mockRes();

    await updateDriver(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});
