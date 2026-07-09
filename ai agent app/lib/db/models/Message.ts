import mongoose, { Schema, type InferSchemaType, type Model } from 'mongoose';

const MessageSchema = new Schema(
  {
    projectId: { type: String, required: true, index: true },
    role: { type: String, enum: ['user', 'assistant'], required: true },
    content: { type: String, required: true },
  },
  { timestamps: true },
);

export type MessageDoc = InferSchemaType<typeof MessageSchema>;

export const Message: Model<MessageDoc> =
  (mongoose.models.Message as Model<MessageDoc>) ||
  mongoose.model<MessageDoc>('Message', MessageSchema);
