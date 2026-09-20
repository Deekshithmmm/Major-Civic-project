const BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'

/**
 * Encodes a point as a geohash. Module 2 stores location this way on purpose: the uploader picks
 * a point on a map and only this coarse cell is sent, so the server never receives a precise
 * position and there is no exact location to subpoena or leak (spec 2.3).
 *
 * Precision 6 is a cell of roughly 1.2km x 0.6km — deliberately coarser than the spec's 500m
 * floor, since for a corruption report an over-precise location points at the person who filmed.
 */
export function encodeGeohash(lat: number, lng: number, precision = 6): string {
  let [latMin, latMax, lngMin, lngMax] = [-90, 90, -180, 180]
  let hash = ''
  let bits = 0
  let value = 0
  let evenBit = true

  while (hash.length < precision) {
    if (evenBit) {
      const mid = (lngMin + lngMax) / 2
      if (lng >= mid) {
        value = (value << 1) + 1
        lngMin = mid
      } else {
        value = value << 1
        lngMax = mid
      }
    } else {
      const mid = (latMin + latMax) / 2
      if (lat >= mid) {
        value = (value << 1) + 1
        latMin = mid
      } else {
        value = value << 1
        latMax = mid
      }
    }
    evenBit = !evenBit

    if (++bits === 5) {
      hash += BASE32[value]
      bits = 0
      value = 0
    }
  }

  return hash
}

/** Approximate size of a precision-6 cell, for telling the user what is actually being sent. */
export const GEOHASH_CELL_DESCRIPTION = 'about 1 km across'
