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
    console.error("Ledger Read Error:", err);
    return {};
  }
};

function getHammingDistance(hash1: string, hash2: string) {
  let distance = 0;
  for (let i = 0; i < hash1.length; i++) {
    if (hash1[i] !== hash2[i]) distance++;
  }
  return distance;
}

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
      // Non-image file or visual hash fallback
    }

    const ledger = getLedger();

    if (ledger[exactHash]) {
      return NextResponse.json({ status: "verified_exact", record: ledger[exactHash] });
    }

    if (visualHash) {
      for (const key in ledger) {
        const dbVisualHash = ledger[key].visualHash;
        if (dbVisualHash) {
          const distance = getHammingDistance(visualHash, dbVisualHash);
          if (distance <= 15) {
            return NextResponse.json({
              status: "verified_transformed",
              record: ledger[key],
              message: `Visual match confirmed (Distance: ${distance}). File data was modified, but origin is verified.`
            });
          }
        }
      }
    }

    return NextResponse.json({
      status: "unverified",
      message: "No match found on the ledger."
    });

  } catch (error: any) {
    console.error("VERIFY API CRASHED:", error.message); 
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
