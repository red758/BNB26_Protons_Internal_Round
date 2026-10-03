import { NextResponse } from 'next/server';
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import Jimp from 'jimp';

const getLedger = () => {
  const filePath = path.join(process.cwd(), 'ledger.json');
  try {
    if (!fs.existsSync(filePath)) {
      fs.writeFileSync(filePath, JSON.stringify({}));
    }
    const data = fs.readFileSync(filePath, 'utf8');
    return data.trim() === "" ? {} : JSON.parse(data);
  } catch (err) {
    return {};
  }
};

export async function POST(req: Request) {
  try {
    const formData = await req.formData();
    const file = formData.get('file') as Blob;
    if (!file) return NextResponse.json({ error: "No file" }, { status: 400 });

    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    
    const exactHash = crypto.createHash('sha256').update(buffer).digest('hex');
    
    let visualHash = '';
    try {
      const image = await Jimp.read(buffer);
      visualHash = image.hash(2);
    } catch {
      // Non-image file fallback
    }

    const ledger = getLedger();

    ledger[exactHash] = {
      visualHash: visualHash,
      model: formData.get('model')?.toString() || "ModelLedger AI",
      trustLevel: "Verified Trusted Provider",
      action: formData.get('action')?.toString() || "Generated Origin",
      timestamp: new Date().toISOString()
    };

    const filePath = path.join(process.cwd(), 'ledger.json');
    fs.writeFileSync(filePath, JSON.stringify(ledger, null, 2));

    return NextResponse.json({ status: "success", hash: exactHash });

  } catch (error: any) {
    console.error("REGISTER API CRASHED:", error.message);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
