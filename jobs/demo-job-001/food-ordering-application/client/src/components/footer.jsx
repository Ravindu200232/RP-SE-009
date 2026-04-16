import {
  AiOutlineFacebook,
  AiOutlineTwitter,
  AiOutlineInstagram,
} from "react-icons/ai";

export default function Footer() {
  return (
    <footer className="w-screen bg-gray-900 text-white py-10">
      <div className="max-w-6xl mx-auto flex flex-wrap justify-center md:justify-between px-6 md:px-12 gap-8">
        {/* Company Section */}
        <div className="w-full sm:w-[45%] md:w-1/4 text-center md:text-left">
          <h1 className="text-xl font-semibold mb-4">Company</h1>
          <ul className="space-y-2 text-gray-400">
            <li>
              <a href="#" className="hover:text-white">
                Contact Us
              </a>
            </li>
            <li>
              <a href="#" className="hover:text-white">
                Our Services
              </a>
            </li>
            <li>
              <a href="#" className="hover:text-white">
                Privacy Policy
              </a>
            </li>
          </ul>
        </div>

        {/* Support Section */}
        <div className="w-full sm:w-[45%] md:w-1/4 text-center md:text-left">
          <h1 className="text-xl font-semibold mb-4">Support</h1>
          <ul className="space-y-2 text-gray-400">
            <li>
              <a href="#" className="hover:text-white">
                FAQs
              </a>
            </li>
            <li>
              <a href="#" className="hover:text-white">
                Shipping & Returns
              </a>
            </li>
            <li>
              <a href="#" className="hover:text-white">
                Terms & Conditions
              </a>
            </li>
          </ul>
        </div>

        {/* Contact Section */}
        <div className="w-full sm:w-[45%] md:w-1/4 text-center md:text-left">
          <h1 className="text-xl font-semibold mb-4">Get in Touch</h1>
          <p className="text-gray-400">Email: support@foodOrder.com</p>
          <p className="text-gray-400">Phone: +94789840996</p>
          <p className="text-gray-400">Location: 123 colombe Street, NY</p>
        </div>

        {/* Social Media Section */}
        <div className="w-full sm:w-[45%] md:w-1/4 text-center md:text-left">
          <h1 className="text-xl font-semibold mb-4">Follow Us</h1>
          <div className="flex justify-center md:justify-start space-x-6">
            <a href="#" className="text-gray-400 hover:text-white text-2xl">
              <AiOutlineFacebook />
            </a>
            <a href="#" className="text-gray-400 hover:text-white text-2xl">
              <AiOutlineTwitter />
            </a>
            <a href="#" className="text-gray-400 hover:text-white text-2xl">
              <AiOutlineInstagram />
            </a>
          </div>
        </div>
      </div>

      {/* Footer Bottom */}
      <div className="text-center text-gray-500 mt-8 text-sm">
        &copy; {new Date().getFullYear()} Food Order. All rights reserved.
      </div>
    </footer>
  );
}
