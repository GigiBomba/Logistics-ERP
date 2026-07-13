import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar"

describe("Avatar", () => {
  it("renders fallback when no image src is provided", () => {
    render(
      <Avatar>
        <AvatarImage />
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>
    )

    expect(screen.getByText("JD")).toBeInTheDocument()
  })

  it("renders image when src is provided", () => {
    render(
      <Avatar>
        <AvatarImage src="/photo.jpg" alt="User" />
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>
    )

    const img = screen.getByRole("img")
    expect(img).toBeInTheDocument()
    expect(img).toHaveAttribute("src", "/photo.jpg")
  })

  it("hides image and shows fallback on error", async () => {
    render(
      <Avatar>
        <AvatarImage src="/broken.jpg" alt="User" />
        <AvatarFallback>FB</AvatarFallback>
      </Avatar>
    )

    const img = screen.getByRole("img")
    fireEvent.error(img)

    await waitFor(() => {
      expect(screen.queryByRole("img")).not.toBeInTheDocument()
    })
    expect(screen.getByText("FB")).toBeInTheDocument()
  })

  it("applies sm size classes", () => {
    const { container } = render(
      <Avatar size="sm">
        <AvatarFallback>SM</AvatarFallback>
      </Avatar>
    )

    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.className).toContain("h-8")
    expect(wrapper.className).toContain("w-8")
  })

  it("applies md size classes", () => {
    const { container } = render(
      <Avatar size="md">
        <AvatarFallback>MD</AvatarFallback>
      </Avatar>
    )

    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.className).toContain("h-10")
    expect(wrapper.className).toContain("w-10")
  })

  it("applies lg size classes", () => {
    const { container } = render(
      <Avatar size="lg">
        <AvatarFallback>LG</AvatarFallback>
      </Avatar>
    )

    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.className).toContain("h-14")
    expect(wrapper.className).toContain("w-14")
  })

  it("applies correct font size for sm fallback", () => {
    render(
      <Avatar size="sm">
        <AvatarFallback>SM</AvatarFallback>
      </Avatar>
    )

    expect(screen.getByText("SM").className).toContain("text-xs")
  })

  it("applies correct font size for lg fallback", () => {
    render(
      <Avatar size="lg">
        <AvatarFallback>LG</AvatarFallback>
      </Avatar>
    )

    expect(screen.getByText("LG").className).toContain("text-lg")
  })
})
