"use client";

import { Search } from "lucide-react";

export default function SearchBar({ value = "", onSearch, placeholder = "Search opportunities…" }) {
  return <form className="searchbar" role="search" onSubmit={(event) => { event.preventDefault(); onSearch?.(value); }}><Search size={17} aria-hidden="true" /><input value={value} onChange={(event) => onSearch?.(event.target.value, { immediate: true })} placeholder={placeholder} aria-label="Search opportunities" /><button type="submit" aria-label="Submit search"><Search size={16} /></button></form>;
}
