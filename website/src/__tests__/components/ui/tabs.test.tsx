import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

describe("Tabs", () => {
  it("renders tabs with defaultValue showing the correct content", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
        <TabsContent value="tab2">Content 2</TabsContent>
      </Tabs>
    )

    expect(screen.getByText("Content 1")).toBeInTheDocument()
    expect(screen.queryByText("Content 2")).not.toBeInTheDocument()
  })

  it("clicking a trigger switches the active tab", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
        <TabsContent value="tab2">Content 2</TabsContent>
      </Tabs>
    )

    fireEvent.click(screen.getByText("Tab 2"))
    expect(screen.queryByText("Content 1")).not.toBeInTheDocument()
    expect(screen.getByText("Content 2")).toBeInTheDocument()
  })

  it("sets aria-selected on the active trigger", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
      </Tabs>
    )

    expect(screen.getByText("Tab 1").closest("button")).toHaveAttribute("aria-selected", "true")
    expect(screen.getByText("Tab 2").closest("button")).toHaveAttribute("aria-selected", "false")
  })

  it("active trigger has data-state active", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
      </Tabs>
    )

    expect(screen.getByText("Tab 1").closest("button")).toHaveAttribute("data-state", "active")
    expect(screen.getByText("Tab 2").closest("button")).toHaveAttribute("data-state", "inactive")
  })

  it("active tab content has data-state active", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
      </Tabs>
    )

    const content = screen.getByText("Content 1").closest('[role="tabpanel"]')
    expect(content).toHaveAttribute("data-state", "active")
  })

  it("forwards className to Tabs", () => {
    const { container } = render(
      <Tabs defaultValue="a" className="custom-tabs">
        <TabsList>
          <TabsTrigger value="a">A</TabsTrigger>
        </TabsList>
      </Tabs>
    )

    expect(container.firstChild).toHaveClass("custom-tabs")
  })

  it("navigates tabs with the right arrow key", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
        <TabsContent value="tab2">Content 2</TabsContent>
      </Tabs>
    )

    fireEvent.keyDown(screen.getByText("Tab 1"), { key: "ArrowRight" })
    expect(screen.queryByText("Content 1")).not.toBeInTheDocument()
    expect(screen.getByText("Content 2")).toBeInTheDocument()
  })

  it("wraps around with the left arrow key", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
        <TabsContent value="tab2">Content 2</TabsContent>
      </Tabs>
    )

    fireEvent.keyDown(screen.getByText("Tab 1"), { key: "ArrowLeft" })
    expect(screen.getByText("Content 2")).toBeInTheDocument()
  })

  it("jumps to the first tab with the Home key", () => {
    render(
      <Tabs defaultValue="tab2">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
        <TabsContent value="tab2">Content 2</TabsContent>
      </Tabs>
    )

    fireEvent.keyDown(screen.getByText("Tab 2"), { key: "Home" })
    expect(screen.getByText("Content 1")).toBeInTheDocument()
  })

  it("jumps to the last tab with the End key", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
        <TabsContent value="tab2">Content 2</TabsContent>
      </Tabs>
    )

    fireEvent.keyDown(screen.getByText("Tab 1"), { key: "End" })
    expect(screen.getByText("Content 2")).toBeInTheDocument()
  })

  it("supports controlled mode with onValueChange", () => {
    const onChange = vi.fn()
    render(
      <Tabs defaultValue="tab1" value="tab1" onValueChange={onChange}>
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
      </Tabs>
    )

    fireEvent.click(screen.getByText("Tab 2"))
    expect(onChange).toHaveBeenCalledWith("tab2")
  })

  it("throws when a trigger is used outside Tabs", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {})
    expect(() => render(<TabsTrigger value="a">A</TabsTrigger>)).toThrow(
      "Tabs compound components must be used within a <Tabs />"
    )
    spy.mockRestore()
  })
})
