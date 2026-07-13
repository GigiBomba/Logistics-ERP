import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { SearchInput } from "@/components/shared/search-input"

describe("SearchInput", () => {
  it("renders input with placeholder", () => {
    render(<SearchInput value="" onChange={() => {}} placeholder="Search items..." />)
    expect(screen.getByPlaceholderText("Search items...")).toBeInTheDocument()
  })

  it("uses default placeholder when none provided", () => {
    render(<SearchInput value="" onChange={() => {}} />)
    expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument()
  })

  it("calls onChange when typing", () => {
    const handleChange = vi.fn()
    render(<SearchInput value="" onChange={handleChange} />)

    const input = screen.getByRole("textbox")
    fireEvent.change(input, { target: { value: "test" } })

    expect(handleChange).toHaveBeenCalledWith("test")
  })

  it("renders clear button when value is non-empty", () => {
    render(<SearchInput value="something" onChange={() => {}} />)
    expect(screen.getByRole("button", { name: /clear search/i })).toBeInTheDocument()
  })

  it("does not render clear button when value is empty", () => {
    render(<SearchInput value="" onChange={() => {}} />)
    expect(screen.queryByRole("button", { name: /clear search/i })).not.toBeInTheDocument()
  })

  it("calls onChange with empty string and onClear when clear button clicked", () => {
    const handleChange = vi.fn()
    const handleClear = vi.fn()

    render(<SearchInput value="search term" onChange={handleChange} onClear={handleClear} />)

    const clearButton = screen.getByRole("button", { name: /clear search/i })
    fireEvent.click(clearButton)

    expect(handleChange).toHaveBeenCalledWith("")
    expect(handleClear).toHaveBeenCalled()
  })

  it("renders search icon", () => {
    const { container } = render(<SearchInput value="" onChange={() => {}} />)
    const svg = container.querySelector("svg")
    expect(svg).toBeInTheDocument()
  })
})
