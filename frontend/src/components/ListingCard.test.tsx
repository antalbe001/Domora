import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Listing } from '../lib/chatStream'
import { ListingCard } from './ListingCard'

function listing(overrides: Partial<Listing> = {}): Listing {
  return {
    reference: 'V2424',
    transaction: 'sale',
    title: 'V2424 – Appartamento',
    url: 'https://example.test/annunci/v2424/',
    description: null,
    price_eur: 115000,
    property_type: 'Appartamento',
    address: 'Via Roma 1',
    city: 'Pordenone',
    province: 'PN',
    surface_sqm: 109,
    bedrooms: 2,
    bathrooms: 1,
    floor_label: '3',
    energy_class: 'D',
    image_url: null,
    ...overrides,
  }
}

describe('ListingCard', () => {
  it('links to the original listing on the agency site', () => {
    render(<ListingCard listing={listing()} />)

    expect(screen.getByRole('link')).toHaveAttribute(
      'href',
      'https://example.test/annunci/v2424/',
    )
  })

  it('shows the price, the place and the reference', () => {
    render(<ListingCard listing={listing()} />)

    expect(screen.getByText('115.000 €')).toBeInTheDocument()
    expect(screen.getByText(/Pordenone \(PN\)/)).toBeInTheDocument()
    expect(screen.getByText('V2424')).toBeInTheDocument()
  })

  it('marks a rent price as monthly', () => {
    render(<ListingCard listing={listing({ transaction: 'rent', price_eur: 500 })} />)

    expect(screen.getByText('500 €/mese')).toBeInTheDocument()
  })

  it('says so when there is no price rather than showing nothing', () => {
    render(<ListingCard listing={listing({ price_eur: null })} />)

    expect(screen.getByText('Prezzo su richiesta')).toBeInTheDocument()
  })

  it('leaves out the facts it does not know', () => {
    render(
      <ListingCard
        listing={listing({ surface_sqm: null, bedrooms: null, energy_class: null })}
      />,
    )

    expect(screen.getByText('1 bagno · piano 3')).toBeInTheDocument()
  })
})
