// Repairs hot and dead photosites in Bayer raw data, the way raw converters
// such as Adobe's do, without a calibration file.

#pragma once

class LibRaw;

namespace stack
{

// The default threshold, in raw units. The 5D Mark II is 14-bit: about 1024
// black to 15000 white.
constexpr int kDefaultMinJump = 256;

// Detects and repairs hot and dead photosites in place. Call it after
// LibRaw::unpack() and before LibRaw::dcraw_process().
//
// A photosite is a defect when two things are true:
// - It is much brighter or darker than all 8 neighbours of its colour. The
//   threshold grows with the local contrast, so that edges and texture are
//   left alone, and with the signal, so that photon noise in bright areas is
//   left alone too.
// - The 4 photosites touching it, of the other colours, are not raised with
//   it. Real light, even a glint on a grainy surface, passes through the lens
//   and spreads onto them; a defect does not.
// A defect is replaced with the median of its 8 neighbours of the same colour.
//
// Returns the number of repaired photosites; 0 for data that is not Bayer
// (sRAW/mRAW, X-Trans, ...), which is left untouched.
int repairDefectPixels(LibRaw& raw, int min_jump = kDefaultMinJump);

}  // namespace stack
