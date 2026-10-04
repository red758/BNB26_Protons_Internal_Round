import { NextResponse } from 'next/server';
import Jimp from 'jimp';

export async function POST(req: Request) {
  try {
    const formData = await req.formData();
    const file = formData.get('file') as Blob;
    if (!file) return NextResponse.json({ error: "No file" }, { status: 400 });

    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    const fileStr = buffer.toString('utf8');

    // 1. Metadata / Binary signature check
    const aiSignatures = [
      { regex: /midjourney/i, model: "Midjourney" },
      { regex: /dall-e/i, model: "DALL-E" },
      { regex: /stable diffusion/i, model: "Stable Diffusion" },
      { regex: /comfyui/i, model: "ComfyUI" },
      { regex: /invokeai/i, model: "InvokeAI" },
      { regex: /novelai/i, model: "NovelAI" }
    ];

    let foundModel = "Unknown";
    let isMetadataAI = false;

    for (const sig of aiSignatures) {
      if (sig.regex.test(fileStr)) {
        foundModel = sig.model;
        isMetadataAI = true;
        break;
      }
    }

    let image;
    try {
      image = await Jimp.read(buffer);
    } catch {
      // If it fails to read (e.g. unsupported format or non-image), fallback to metadata only
      if (isMetadataAI) {
         return NextResponse.json({
           status: "success",
           analysis: {
             trustFactor: 0,
             determination: "AI Generated",
             model: foundModel,
             metrics: { avgNoise: 0, avgSaturation: 0, aiScore: 100, metadataFound: true }
           }
         });
      }
      return NextResponse.json({ error: "Could not parse image for analysis" }, { status: 400 });
    }

    // 2. Heuristic calculations (Noise, Variance, Color Space, Uniformity)
    const width = image.bitmap.width;
    const height = image.bitmap.height;

    let totalNoise = 0;
    let totalSaturation = 0;
    let sampleCount = 0;
    const noiseValues: number[] = [];

    // Sample pixels across the image to calculate "smoothness", "color distribution", and "noise uniformity"
    const step = Math.max(1, Math.floor(width / 60));
    for (let y = 0; y < height - 1; y += step) {
      for (let x = 0; x < width - 1; x += step) {
        const idx1 = image.getPixelIndex(x, y);
        const idx2 = image.getPixelIndex(x + 1, y + 1);

        const r1 = image.bitmap.data[idx1];
        const g1 = image.bitmap.data[idx1 + 1];
        const b1 = image.bitmap.data[idx1 + 2];

        const r2 = image.bitmap.data[idx2];
        const g2 = image.bitmap.data[idx2 + 1];
        const b2 = image.bitmap.data[idx2 + 2];

        // Local variation (rough noise/edge estimate)
        const diff = Math.abs(r1 - r2) + Math.abs(g1 - g2) + Math.abs(b1 - b2);
        totalNoise += diff;
        noiseValues.push(diff);

        // Saturation estimate
        const max = Math.max(r1, g1, b1);
        const min = Math.min(r1, g1, b1);
        const saturation = max === 0 ? 0 : (max - min) / max;
        totalSaturation += saturation;

        sampleCount++;
      }
    }

    const avgNoise = sampleCount > 0 ? totalNoise / sampleCount : 0;
    const avgSaturation = sampleCount > 0 ? totalSaturation / sampleCount : 0;

    // Calculate Noise Uniformity (Standard Deviation of local variance)
    // Real images have natural variance in noise (e.g. shadows are noisier). AI is often too perfectly uniform.
    let noiseVarianceSum = 0;
    for (const n of noiseValues) {
        noiseVarianceSum += Math.pow(n - avgNoise, 2);
    }
    const noiseStdDev = sampleCount > 0 ? Math.sqrt(noiseVarianceSum / sampleCount) : 0;

    // 3. Base AI Probability Score (0 to 100)
    let aiScore = 20; // Start with a base suspicion for web images

    if (isMetadataAI) {
      aiScore = 100;
    } else {
      // 1. Smoothness Penalty: AI (and heavy compression) smooths out natural sensor grain
      if (avgNoise < 18) aiScore += 45; 
      else if (avgNoise > 40) aiScore += 25; // Overly sharpened

      // 2. Saturation Penalty: AI models often push vibrant, unnatural color palettes
      if (avgSaturation > 0.40) aiScore += 35;
      else if (avgSaturation > 0.30) aiScore += 15;

      // 3. Uniformity Penalty: If the noise deviation is unnaturally low compared to the average noise
      if (noiseStdDev < (avgNoise * 0.6)) aiScore += 30; // Unnaturally uniform texture
      
      // 4. Entropy variance: Distance from "ideal" natural noise (~24)
      const variationScore = Math.abs(24 - avgNoise);
      aiScore += Math.min(40, variationScore * 2.5);
    }

    // Bound score
    aiScore = Math.max(0, Math.min(100, aiScore));

    // 4. Determine Trust Factor and Model Guess based on score
    let trustFactor = 0;
    let finalModel = foundModel;
    let determination = "";

    if (aiScore >= 70) {
        trustFactor = 0; // AI
        determination = "AI Generated";
        if (finalModel === "Unknown") {
            // Approximate model based on visual heuristics if no metadata
            if (avgSaturation > 0.5) finalModel = "Midjourney (Approximated)";
            else if (avgNoise < 10) finalModel = "DALL-E (Approximated)";
            else finalModel = "Stable Diffusion (Approximated)";
        }
    } else if (aiScore <= 35) {
        trustFactor = 100; // Authentic
        determination = "Authentic (Not AI)";
        finalModel = "Camera/Original";
    } else {
        // Map the middle range (36-69) to 60-70 trust factor linearly
        // 36 -> 70, 69 -> 60
        const ratio = (aiScore - 35) / (70 - 35); // 0 to 1
        trustFactor = Math.round(70 - (ratio * 10)); // 70 down to 60
        determination = "Unsure / Mixed";
        finalModel = "Unknown/Edited";
    }

    return NextResponse.json({
      status: "success",
      analysis: {
        trustFactor,
        determination,
        model: finalModel,
        metrics: {
          avgNoise: Math.round(avgNoise * 100) / 100,
          avgSaturation: Math.round(avgSaturation * 100) / 100,
          aiScore: Math.round(aiScore),
          metadataFound: isMetadataAI
        }
      }
    });

  } catch (error: any) {
    console.error("VERIFY API CRASHED:", error.message);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
