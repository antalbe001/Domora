import type { Listing } from './chatStream'

const euro = new Intl.NumberFormat('it-IT', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

export function formatPrice(listing: Listing): string {
  if (listing.price_eur === null) return 'Prezzo su richiesta'
  const amount = euro.format(listing.price_eur)
  return listing.transaction === 'rent' ? `${amount}/mese` : amount
}

/** The facts worth showing on a card, skipping the ones we don't know. */
export function listingFacts(listing: Listing): string[] {
  const facts: string[] = []
  if (listing.surface_sqm !== null) facts.push(`${listing.surface_sqm} m²`)
  if (listing.bedrooms !== null)
    facts.push(listing.bedrooms === 1 ? '1 camera' : `${listing.bedrooms} camere`)
  if (listing.bathrooms !== null)
    facts.push(listing.bathrooms === 1 ? '1 bagno' : `${listing.bathrooms} bagni`)
  if (listing.floor_label !== null) facts.push(`piano ${listing.floor_label}`)
  if (listing.energy_class !== null) facts.push(`classe ${listing.energy_class}`)
  return facts
}

export function listingPlace(listing: Listing): string {
  return [listing.city, listing.province && `(${listing.province})`]
    .filter(Boolean)
    .join(' ')
}
