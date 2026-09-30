import type { Listing } from '../lib/chatStream'
import { formatPrice, listingFacts, listingPlace } from '../lib/format'

export function ListingCard({ listing }: { listing: Listing }) {
  const place = listingPlace(listing)

  return (
    <a
      href={listing.url}
      target="_blank"
      rel="noreferrer"
      className="group flex gap-3 rounded-xl border border-stone-200 bg-white p-3 transition hover:border-stone-300 hover:shadow-sm"
    >
      {listing.image_url ? (
        <img
          src={listing.image_url}
          alt=""
          loading="lazy"
          className="h-20 w-24 shrink-0 rounded-lg object-cover"
        />
      ) : (
        <div className="grid h-20 w-24 shrink-0 place-items-center rounded-lg bg-stone-100 text-stone-400">
          <svg viewBox="0 0 24 24" fill="none" className="h-7 w-7" aria-hidden>
            <path
              d="M3 10.5 12 4l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-9.5Z"
              stroke="currentColor"
              strokeWidth="1.5"
            />
          </svg>
        </div>
      )}

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="font-medium text-stone-900">{formatPrice(listing)}</span>
          <span className="shrink-0 font-mono text-xs text-stone-400">
            {listing.reference}
          </span>
        </div>

        <p className="truncate text-sm text-stone-600">
          {listing.property_type ?? 'Immobile'}
          {place && ` · ${place}`}
        </p>

        <p className="mt-1 text-xs text-stone-500">{listingFacts(listing).join(' · ')}</p>
      </div>
    </a>
  )
}
