import nodemailer from "nodemailer";
import axios from "axios";

// Email Transporter Configuration
const transporter = nodemailer.createTransport({
  service: "gmail",
  host: "smtp.gmail.com",
  port: 587,
  secure: false,
  auth: {
    user: "ravindusubasinha082@gmail.com",
    pass: "mbvi tbqp spgl lmia", // Use your app password
  },
});

export async function EmailSender(req, res) {
  try {
    const {
      orderId,
      driverId,
      driverName,
      driverPhone,
      driverEmail,
      customerEmail,
      address,
      phone,
      status,
      estimatedTime,
      lat,
      lng,
      itemName,
      qty,
      totalPrice,
      restaurantId, // Make sure this is sent in the req.body
    } = req.body;

    // Fetch restaurant info
    const restaurantServiceUrl = process.env.RESTAURANT_SERVICE_URL || 'http://localhost:3002';
    const restaurantRes = await axios.get(`${restaurantServiceUrl}/api/v1/restaurant/getOne/${restaurantId}`);
    const restaurant = restaurantRes.data?.data;

    const locationLink = `https://www.google.com/maps?q=${lat},${lng}`;

    // Email to Driver
    const driverMailOptions = {
      from: '"Food Delivery App" <ravindusubasinha082@gmail.com>',
      to: driverEmail,
      subject: `New Delivery Assigned - Order ${orderId}`,
      html: `
        <h2>New Order Delivery</h2>
        <p>Hello <strong>${driverName}</strong>,</p>
        <p>You have been assigned to deliver the following order:</p>
        <ul>
          <li><strong>Order ID:</strong> ${orderId}</li>
          <li><strong>Item:</strong> ${itemName}</li>
          <li><strong>Quantity:</strong> ${qty}</li>
          <li><strong>Total Price:</strong> Rs. ${totalPrice}</li>
          <li><strong>Customer Address:</strong> ${address}</li>
          <li><strong>Customer Phone:</strong> ${phone}</li>
          <li><strong>Estimated Delivery Time:</strong> ${new Date(estimatedTime).toLocaleString()}</li>
          <li><strong>Location Link:</strong> <a href="${locationLink}" target="_blank">View on Map</a></li>
        </ul>
        <h3>Restaurant Info</h3>
        <p><strong>${restaurant?.name}</strong></p>
        <p>Owned by: <strong>${restaurant?.ownerName}</strong></p>
        <p>📍 ${restaurant?.address}</p>
        <p>📞 ${restaurant?.phone}</p>
        <p>Please deliver the item on time. Thank you!</p>
      `,
    };

    // Email to Customer
    const customerMailOptions = {
      from: '"Food Delivery App" <ravindusubasinha082@gmail.com>',
      to: customerEmail,
      subject: `Your Order ${orderId} is on the way!`,
      html: `
        <h2>Order Update</h2>
        <p>Hi there,</p>
        <p>Your order has been picked up and is on the way! Here are your delivery details:</p>
        <ul>
          <li><strong>Order ID:</strong> ${orderId}</li>
          <li><strong>Item:</strong> ${itemName}</li>
          <li><strong>Quantity:</strong> ${qty}</li>
          <li><strong>Total Price:</strong> Rs. ${totalPrice}</li>
          <li><strong>Driver Name:</strong> ${driverName}</li>
          <li><strong>Driver Phone:</strong> ${driverPhone}</li>
          <li><strong>Estimated Delivery Time:</strong> ${new Date(estimatedTime).toLocaleString()}</li>
          <li><strong>Track Location:</strong> <a href="${locationLink}" target="_blank">Live Location</a></li>
        </ul>
        <h3>Restaurant Info</h3>
        <p><strong>${restaurant?.name}</strong></p>
        <p>Owned by: <strong>${restaurant?.ownerName}</strong></p>
        <p>📍 ${restaurant?.address}</p>
        <p>📞 ${restaurant?.phone}</p>
        <p>Thank you for ordering with us!</p>
      `,
    };

    // Send emails
    await transporter.sendMail(driverMailOptions);
    await transporter.sendMail(customerMailOptions);

    res.status(200).json({ message: "Emails sent successfully" });
  } catch (error) {
    console.error("Email sending failed:", error.message);
    res.status(500).json({ message: "Failed to send email", error });
  }
}
