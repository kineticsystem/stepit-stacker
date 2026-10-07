#include "defect_pixels.hh"

#include <libraw/libraw.h>

#include <algorithm>
#include <vector>

namespace stack
{

namespace
{

// In a Bayer pattern the nearest photosites of the same colour are always 2 away.
const int kSameColour[8][2] = { { -2, -2 }, { -2, 0 }, { -2, 2 }, { 0, -2 }, { 0, 2 }, { 2, -2 }, { 2, 0 }, { 2, 2 } };
// The photosites touching one, which have the other colours.
const int kTouching[4][2] = { { -1, 0 }, { 1, 0 }, { 0, -1 }, { 0, 1 } };

// The margin grows with the signal of the brightest neighbour above black,
// because photon noise does: 1/8 of it.
constexpr int kSignalDivisor = 8;
// A touching photosite raised by more than this fraction of the candidate's
// own excess means real light, spread by the lens, not a defect.
constexpr int kSpreadDivisor = 4;

class Neighbourhood
{
public:
  Neighbourhood(const std::vector<ushort>& data, size_t pitch, int r, int c)
  {
    for (int k = 0; k < 8; ++k)
    {
      values_[k] = data[(r + kSameColour[k][0]) * pitch + c + kSameColour[k][1]];
    }
    std::sort(values_, values_ + 8);
  }
  int min() const
  {
    return values_[0];
  }
  int max() const
  {
    return values_[7];
  }
  int median() const
  {
    return (values_[3] + values_[4]) / 2;
  }

private:
  int values_[8];
};

}  // namespace

int repairDefectPixels(LibRaw& raw, int min_jump)
{
  auto& rd = raw.imgdata.rawdata;
  const auto& s = raw.imgdata.sizes;
  const unsigned filters = raw.imgdata.idata.filters;
  // Not Bayer: sRAW/mRAW or X-Trans.
  if (!rd.raw_image || filters == 0 || filters == 9)
  {
    return 0;
  }

  const size_t pitch = s.raw_pitch / sizeof(ushort);  // raw_pitch is in bytes.
  const int black = int(raw.imgdata.color.black);
  // Detect on an untouched copy, so a repaired photosite never influences its neighbours.
  const std::vector<ushort> src(rd.raw_image, rd.raw_image + pitch * s.raw_height);

  int repaired = 0;
  // 3 photosites from the edges, so the touching photosites have their 8 neighbours too.
  for (int r = s.top_margin + 3; r < s.top_margin + s.height - 3; ++r)
  {
    for (int c = s.left_margin + 3; c < s.left_margin + s.width - 3; ++c)
    {
      const Neighbourhood around(src, pitch, r, c);
      const int v = src[r * pitch + c];
      const int margin = std::max({ min_jump, around.max() - around.min(), (around.max() - black) / kSignalDivisor });
      if (v <= around.max() + margin && v >= around.min() - margin)
      {
        continue;
      }

      // Even a glint smaller than a photosite passes through the lens, which
      // spreads it onto the touching photosites. A defect stands alone.
      const int excess = v - around.median();
      bool spread = false;
      for (const auto& offset : kTouching)
      {
        const int tr = r + offset[0], tc = c + offset[1];
        const int touching_excess = src[tr * pitch + tc] - Neighbourhood(src, pitch, tr, tc).median();
        spread = spread ||
                 (excess > 0 ? touching_excess * kSpreadDivisor > excess : touching_excess * kSpreadDivisor < excess);
      }
      if (!spread)
      {
        rd.raw_image[r * pitch + c] = ushort(around.median());
        ++repaired;
      }
    }
  }
  return repaired;
}

}  // namespace stack
