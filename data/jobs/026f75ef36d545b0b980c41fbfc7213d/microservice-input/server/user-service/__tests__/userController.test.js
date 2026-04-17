// Mock all dependencies before any imports (babel-jest hoists these)
jest.mock('../models/users.js', () => {
  const MockUser = jest.fn().mockImplementation((data) => ({
    ...data,
    _id: 'user123',
    save: jest.fn().mockResolvedValue({ _id: 'user123', ...data }),
  }));
  MockUser.findOne = jest.fn();
  MockUser.find    = jest.fn();
  MockUser.updateOne = jest.fn();
  MockUser.deleteOne = jest.fn();
  return { __esModule: true, default: MockUser };
});

jest.mock('../models/otp.js', () => {
  const MockOTP = jest.fn().mockImplementation((data) => ({
    ...data,
    save: jest.fn().mockResolvedValue(true),
  }));
  MockOTP.findOne  = jest.fn();
  MockOTP.deleteOne = jest.fn();
  return { __esModule: true, default: MockOTP };
});

jest.mock('../models/driver.js', () => {
  const MockDriver = jest.fn();
  MockDriver.findOne = jest.fn();
  return { __esModule: true, default: MockDriver };
});

jest.mock('bcrypt', () => ({
  hashSync:    jest.fn().mockReturnValue('hashedpassword'),
  compareSync: jest.fn(),
}));

jest.mock('jsonwebtoken', () => ({
  sign: jest.fn().mockReturnValue('mock.jwt.token'),
}));

jest.mock('nodemailer', () => ({
  createTransport: jest.fn().mockReturnValue({
    sendMail: jest.fn((opts, cb) => cb(null, { messageId: 'test-123' })),
  }),
}));

jest.mock('axios', () => ({ get: jest.fn(), post: jest.fn() }));

import User   from '../models/users.js';
import Driver from '../models/driver.js';
import bcrypt from 'bcrypt';
import {
  createUser, userLogin, getUsers,
  getOneUser, updateUser, deleteUser, changePassword,
} from '../controllers/userController.js';

// ── helpers ──────────────────────────────────────────────────────────────────
const mockReq = (overrides = {}) => ({
  body: {}, params: {}, query: {}, user: null,
  header: jest.fn(), ...overrides,
});
const mockRes = () => {
  const res = {};
  res.status = jest.fn().mockReturnValue(res);
  res.json   = jest.fn().mockReturnValue(res);
  return res;
};

beforeEach(() => jest.clearAllMocks());

// ── createUser ────────────────────────────────────────────────────────────────
describe('createUser', () => {
  it('registers a new user successfully', async () => {
    const req = mockReq({ body: { email: 'new@example.com', password: 'pass123', firstName: 'John', role: 'customer' } });
    const res = mockRes();
    User.findOne.mockResolvedValue(null);

    await createUser(req, res);

    expect(User.findOne).toHaveBeenCalledWith({ email: 'new@example.com' });
    expect(res.json).toHaveBeenCalledWith({ message: 'Uses Added!' });
  });

  it('returns 401 when email already in use', async () => {
    const req = mockReq({ body: { email: 'taken@example.com', password: 'pass' } });
    const res = mockRes();
    User.findOne.mockResolvedValue({ email: 'taken@example.com' });

    await createUser(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
    expect(res.json).toHaveBeenCalledWith({ message: 'Email is Already use' });
  });

  it('returns 500 on database error', async () => {
    const req = mockReq({ body: { email: 'err@example.com', password: 'pass' } });
    const res = mockRes();
    User.findOne.mockRejectedValue(new Error('DB error'));

    await createUser(req, res);

    expect(res.status).toHaveBeenCalledWith(500);
  });
});

// ── userLogin ─────────────────────────────────────────────────────────────────
describe('userLogin', () => {
  const mockUser = { _id: 'u1', email: 'u@e.com', password: 'hashed', role: 'customer', firstName: 'A', lastName: 'B' };

  it('logs in successfully with correct credentials', async () => {
    const req = mockReq({ body: { email: 'u@e.com', password: 'correct' } });
    const res = mockRes();
    User.findOne.mockResolvedValue(mockUser);
    Driver.findOne.mockResolvedValue(null);
    bcrypt.compareSync.mockReturnValue(true);

    await userLogin(req, res);

    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Login successfully', token: 'mock.jwt.token' }),
    );
  });

  it('returns 404 for wrong password', async () => {
    const req = mockReq({ body: { email: 'u@e.com', password: 'wrong' } });
    const res = mockRes();
    User.findOne.mockResolvedValue(mockUser);
    Driver.findOne.mockResolvedValue(null);
    bcrypt.compareSync.mockReturnValue(false);

    await userLogin(req, res);

    expect(res.status).toHaveBeenCalledWith(404);
    expect(res.json).toHaveBeenCalledWith({ message: 'Password incorrect ,please try again!' });
  });

  it('returns 404 when user does not exist', async () => {
    const req = mockReq({ body: { email: 'ghost@e.com', password: 'pass' } });
    const res = mockRes();
    User.findOne.mockResolvedValue(null);
    Driver.findOne.mockResolvedValue(null);

    await userLogin(req, res);

    expect(res.status).toHaveBeenCalledWith(404);
    expect(res.json).toHaveBeenCalledWith({ message: 'user not found please try again!' });
  });
});

// ── getUsers ──────────────────────────────────────────────────────────────────
describe('getUsers', () => {
  it('returns all users for admin', async () => {
    const req = mockReq({ user: { role: 'admin' } });
    const res = mockRes();
    User.find.mockResolvedValue([{ email: 'a@a.com' }]);

    await getUsers(req, res);

    expect(res.json).toHaveBeenCalledWith([{ email: 'a@a.com' }]);
  });

  it('returns 403 for non-admin logged-in user', async () => {
    const req = mockReq({ user: { role: 'customer' } });
    const res = mockRes();

    await getUsers(req, res);

    expect(res.status).toHaveBeenCalledWith(403);
  });

  it('returns 403 when not logged in', async () => {
    const req = mockReq({ user: null });
    const res = mockRes();

    await getUsers(req, res);

    expect(res.status).toHaveBeenCalledWith(403);
  });
});

// ── getOneUser ────────────────────────────────────────────────────────────────
describe('getOneUser', () => {
  it('returns user when authenticated', async () => {
    const user = { _id: 'u1', email: 'a@a.com' };
    const req  = mockReq({ params: { id: 'u1' }, user: { role: 'customer' } });
    const res  = mockRes();
    User.findOne.mockResolvedValue(user);

    await getOneUser(req, res);

    expect(res.json).toHaveBeenCalledWith(user);
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ params: { id: 'u1' }, user: null });
    const res = mockRes();

    await getOneUser(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });

  it('returns 404 when user not found', async () => {
    const req = mockReq({ params: { id: 'noone' }, user: { role: 'admin' } });
    const res = mockRes();
    User.findOne.mockResolvedValue(null);

    await getOneUser(req, res);

    expect(res.status).toHaveBeenCalledWith(404);
  });
});

// ── updateUser ────────────────────────────────────────────────────────────────
describe('updateUser', () => {
  it('updates user when authenticated', async () => {
    const req = mockReq({ params: { id: 'u1' }, body: { firstName: 'Updated' }, user: { role: 'customer' } });
    const res = mockRes();
    User.updateOne.mockResolvedValue({ modifiedCount: 1 });

    await updateUser(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'User updated successfully' });
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ params: { id: 'u1' }, body: {}, user: null });
    const res = mockRes();

    await updateUser(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});

// ── deleteUser ────────────────────────────────────────────────────────────────
describe('deleteUser', () => {
  it('deletes user when authenticated', async () => {
    const req = mockReq({ params: { id: 'u1' }, user: { role: 'admin' } });
    const res = mockRes();
    User.deleteOne.mockResolvedValue({ deletedCount: 1 });

    await deleteUser(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'User deleted successfully' });
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ params: { id: 'u1' }, user: null });
    const res = mockRes();

    await deleteUser(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});

// ── changePassword ────────────────────────────────────────────────────────────
describe('changePassword', () => {
  it('changes password with correct old password', async () => {
    const req = mockReq({
      params: { id: 'u1' },
      body: { oldPassword: 'oldpass', newPassword: 'newpass' },
      user: { id: 'u1' },
    });
    const res = mockRes();
    User.findOne.mockResolvedValue({ _id: 'u1', password: 'hashed' });
    bcrypt.compareSync.mockReturnValue(true);
    User.updateOne.mockResolvedValue({ modifiedCount: 1 });

    await changePassword(req, res);

    expect(res.json).toHaveBeenCalledWith({ message: 'User password updated successfully' });
  });

  it('returns 401 for incorrect old password', async () => {
    const req = mockReq({
      params: { id: 'u1' },
      body: { oldPassword: 'wrongold', newPassword: 'new' },
      user: { id: 'u1' },
    });
    const res = mockRes();
    User.findOne.mockResolvedValue({ _id: 'u1', password: 'hashed' });
    bcrypt.compareSync.mockReturnValue(false);

    await changePassword(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
    expect(res.json).toHaveBeenCalledWith({ message: 'Old password is incorrect' });
  });

  it('returns 401 when not logged in', async () => {
    const req = mockReq({ params: { id: 'u1' }, body: {}, user: null });
    const res = mockRes();

    await changePassword(req, res);

    expect(res.status).toHaveBeenCalledWith(401);
  });
});
