// Mock nodemailer before the module is loaded (called at module load time)
jest.mock('nodemailer', () => ({
  createTransport: jest.fn().mockReturnValue({
    sendMail: jest.fn().mockResolvedValue({ messageId: 'msg-123' }),
  }),
}));

jest.mock('axios', () => ({
  get: jest.fn(),
}));

import nodemailer from 'nodemailer';
import axios     from 'axios';
import { EmailSender } from '../controllers/notificationSender.js';

const mockReq = (overrides = {}) => ({
  body: {}, params: {}, user: null, ...overrides,
});
const mockRes = () => {
  const res = {};
  res.status = jest.fn().mockReturnValue(res);
  res.json   = jest.fn().mockReturnValue(res);
  return res;
};

const validBody = {
  orderId:       'ORD0001',
  driverId:      'driver1',
  driverName:    'Kamal Perera',
  driverPhone:   '+94771112233',
  driverEmail:   'kamal@driver.com',
  customerEmail: 'customer@example.com',
  address:       '123 Main St, Colombo',
  phone:         '+94771234567',
  status:        'picked up',
  estimatedTime: '2024-03-22T14:30:00Z',
  lat:           6.9271,
  lng:           79.8612,
  itemName:      'Chicken Rice',
  qty:           2,
  totalPrice:    1100,
  restaurantId:  'rest123',
};

const mockRestaurant = {
  name:      'Spice Garden',
  ownerName: 'Ravi Kumar',
  address:   '45 Galle Road, Colombo',
  phone:     '+94112345678',
};

beforeEach(() => jest.clearAllMocks());

// ── EmailSender ───────────────────────────────────────────────────────────────
describe('EmailSender', () => {
  it('sends emails to both driver and customer on success', async () => {
    const req = mockReq({ body: validBody });
    const res = mockRes();
    axios.get.mockResolvedValue({ data: { data: mockRestaurant } });
    const transporter = nodemailer.createTransport();

    await EmailSender(req, res);

    // Should send 2 emails: one to driver, one to customer
    expect(transporter.sendMail).toHaveBeenCalledTimes(2);
    expect(res.status).toHaveBeenCalledWith(200);
    expect(res.json).toHaveBeenCalledWith({ message: 'Emails sent successfully' });
  });

  it('fetches restaurant info from restaurant service', async () => {
    const req = mockReq({ body: validBody });
    const res = mockRes();
    axios.get.mockResolvedValue({ data: { data: mockRestaurant } });

    await EmailSender(req, res);

    expect(axios.get).toHaveBeenCalledWith(
      expect.stringContaining(`/api/v1/restaurant/getOne/${validBody.restaurantId}`),
    );
  });

  it('sends driver email with correct order details', async () => {
    const req = mockReq({ body: validBody });
    const res = mockRes();
    axios.get.mockResolvedValue({ data: { data: mockRestaurant } });
    const transporter = nodemailer.createTransport();

    await EmailSender(req, res);

    const driverMailCall = transporter.sendMail.mock.calls[0][0];
    expect(driverMailCall.to).toBe(validBody.driverEmail);
    expect(driverMailCall.subject).toContain(validBody.orderId);
  });

  it('sends customer email with correct order details', async () => {
    const req = mockReq({ body: validBody });
    const res = mockRes();
    axios.get.mockResolvedValue({ data: { data: mockRestaurant } });
    const transporter = nodemailer.createTransport();

    await EmailSender(req, res);

    const customerMailCall = transporter.sendMail.mock.calls[1][0];
    expect(customerMailCall.to).toBe(validBody.customerEmail);
    expect(customerMailCall.subject).toContain(validBody.orderId);
  });

  it('returns 500 when restaurant service fails', async () => {
    const req = mockReq({ body: validBody });
    const res = mockRes();
    axios.get.mockRejectedValue(new Error('Restaurant service unreachable'));

    await EmailSender(req, res);

    expect(res.status).toHaveBeenCalledWith(500);
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Failed to send email' }),
    );
  });

  it('returns 500 when email sending fails', async () => {
    const req = mockReq({ body: validBody });
    const res = mockRes();
    axios.get.mockResolvedValue({ data: { data: mockRestaurant } });
    const transporter = nodemailer.createTransport();
    transporter.sendMail.mockRejectedValueOnce(new Error('SMTP error'));

    await EmailSender(req, res);

    expect(res.status).toHaveBeenCalledWith(500);
  });
});
