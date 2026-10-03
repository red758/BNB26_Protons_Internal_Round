import { NextResponse } from 'next/server';
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import Jimp from 'jimp';

// Bulletproof Ledger Reader
const getLedger = () => {
  const filePath = path.join(process.cwd(), 'ledger.json');
  try {
    if (!fs.existsSync(filePath)) {
      fs.writeFileSync(filePath, JSON.stringify({})); // Create it if missing
    }
    const data = fs.readFileSync(filePath, 'utf8');
    return data.trim() === "" ? {} : JSON.parse(data); // Handle empty file
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

    // Calculate Exact Hash
    const exactHash = crypto.createHash('sha256').update(buffer).digest('hex');
    
    // Calculate Visual Hash
    const image = await Jimp.read(buffer);
    const visualHash = image.hash(2);

    const ledger = getLedger();

    if (ledger[exactHash]) {
      return NextResponse.json({ status: "verified_exact", record: ledger[exactHash] });
    }

    for (const key in ledger) {
      const dbVisualHash = ledger[key].visualHash;
      if (dbVisualHash) {
        const distance = getHammingDistance(visualHash, dbVisualHash);
        if (distance <= 15) { // 12 bits of leniency for compression/resizing
          return NextResponse.json({
            status: "verified_transformed",
            record: ledger[key],
            message: `Visual match confirmed (Distance: ${distance}). File data was modified, but origin is verified.`
          });
        }
      }
    }

    return NextResponse.json({
      status: "unverified",
      message: "No match found on the ledger."
    });

  } catch (error: any) {
    // THIS WILL PRINT THE EXACT ERROR IN YOUR TERMINAL
    console.error("VERIFY API CRASHED:", error.message); 
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}