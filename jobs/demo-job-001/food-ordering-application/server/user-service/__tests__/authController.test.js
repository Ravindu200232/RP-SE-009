import {
  checkHasAccount,
  checkAdmin,
  checkCustomer,
  checkRestaurant,
  checkDelivery,
} from '../controllers/authController.js';

describe('authController – role helpers', () => {

  describe('checkHasAccount', () => {
    it('returns true when user is logged in', () => {
      expect(checkHasAccount({ user: { id: '1', role: 'customer' } })).toBe(true);
    });
    it('returns false when user is null', () => {
      expect(checkHasAccount({ user: null })).toBe(false);
    });
    it('returns false when user is undefined', () => {
      expect(checkHasAccount({})).toBe(false);
    });
  });

  describe('checkAdmin', () => {
    it('returns true for admin role', () => {
      expect(checkAdmin({ user: { role: 'admin' } })).toBe(true);
    });
    it('returns false for customer role', () => {
      expect(checkAdmin({ user: { role: 'customer' } })).toBe(false);
    });
    it('returns false for restaurant role', () => {
      expect(checkAdmin({ user: { role: 'restaurant' } })).toBe(false);
    });
    it('returns false for delivery role', () => {
      expect(checkAdmin({ user: { role: 'delivery' } })).toBe(false);
    });
  });

  describe('checkCustomer', () => {
    it('returns true for customer role', () => {
      expect(checkCustomer({ user: { role: 'customer' } })).toBe(true);
    });
    it('returns false for admin role', () => {
      expect(checkCustomer({ user: { role: 'admin' } })).toBe(false);
    });
    it('returns false for restaurant role', () => {
      expect(checkCustomer({ user: { role: 'restaurant' } })).toBe(false);
    });
  });

  describe('checkRestaurant', () => {
    it('returns true for restaurant role', () => {
      expect(checkRestaurant({ user: { role: 'restaurant' } })).toBe(true);
    });
    it('returns false for customer role', () => {
      expect(checkRestaurant({ user: { role: 'customer' } })).toBe(false);
    });
  });

  describe('checkDelivery', () => {
    it('returns true for delivery role', () => {
      expect(checkDelivery({ user: { role: 'delivery' } })).toBe(true);
    });
    it('returns false for customer role', () => {
      expect(checkDelivery({ user: { role: 'customer' } })).toBe(false);
    });
  });
});
