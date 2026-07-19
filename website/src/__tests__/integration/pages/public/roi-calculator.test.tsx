import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import RoiCalculatorPage from "@/pages/public/roi-calculator"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("RoiCalculatorPage", () => {
  it("renders the hero section", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("ROI Calculator")).toBeInTheDocument()
  })

  it("renders the inputs section title", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Fleet Details")).toBeInTheDocument()
    expect(
      screen.getByText("Enter your current operation numbers. Results update automatically.")
    ).toBeInTheDocument()
  })

  it("renders slider input for fleet size", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Fleet size")).toBeInTheDocument()
    const slider = screen.getByDisplayValue("20")
    expect(slider).toBeInTheDocument()
  })

  it("renders number inputs for various parameters", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Number of drivers")).toBeInTheDocument()
    expect(screen.getByText("Monthly trips per vehicle")).toBeInTheDocument()
    expect(screen.getByText("Average revenue per trip")).toBeInTheDocument()
    expect(screen.getByText("Average fuel cost per liter")).toBeInTheDocument()
    expect(screen.getByText("Average distance per trip (km)")).toBeInTheDocument()
    expect(screen.getByText("Number of dispatchers")).toBeInTheDocument()
    expect(screen.getByText("Monthly invoices")).toBeInTheDocument()
  })

  it("renders results section", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Your Estimated Savings")).toBeInTheDocument()
  })

  it("renders average cost per trip stat", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Avg cost per trip")).toBeInTheDocument()
  })

  it("renders average profit per trip stat", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Avg profit per trip")).toBeInTheDocument()
  })

  it("renders monthly profit stat", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Monthly profit")).toBeInTheDocument()
  })

  it("renders fuel savings stat", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Fuel savings / month")).toBeInTheDocument()
  })

  it("renders time savings stat", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Time savings / month")).toBeInTheDocument()
  })

  it("renders admin savings stat", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Admin savings / month")).toBeInTheDocument()
  })

  it("renders total monthly ROI stat", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Total monthly ROI")).toBeInTheDocument()
  })

  it("renders yearly savings stat", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Projected yearly savings")).toBeInTheDocument()
  })

  it("renders assumptions toggle button", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Assumptions & Methodology")).toBeInTheDocument()
  })

  it("shows assumptions content when toggle is clicked", () => {
    render(<RoiCalculatorPage />)
    const toggle = screen.getByText("Assumptions & Methodology")
    fireEvent.click(toggle)
    expect(screen.getByText(/12% reduction in fuel consumption/)).toBeInTheDocument()
    expect(screen.getByText(/8% reduction in distance/)).toBeInTheDocument()
    expect(screen.getByText(/90% reduction in manual coordination/)).toBeInTheDocument()
  })

  it("hides assumptions content when toggle is clicked again", () => {
    render(<RoiCalculatorPage />)
    const toggle = screen.getByText("Assumptions & Methodology")
    fireEvent.click(toggle)
    expect(screen.getByText(/12% reduction in fuel consumption/)).toBeInTheDocument()
    fireEvent.click(toggle)
    expect(screen.queryByText(/12% reduction in fuel consumption/)).not.toBeInTheDocument()
  })

  it("renders CTA section", () => {
    render(<RoiCalculatorPage />)
    expect(screen.getByText("Get a detailed quote")).toBeInTheDocument()
    expect(screen.getByText("Talk to sales")).toBeInTheDocument()
  })

  it("fleet size slider can be changed", () => {
    render(<RoiCalculatorPage />)
    const slider = screen.getByDisplayValue("20") as HTMLInputElement
    fireEvent.change(slider, { target: { value: "35" } })
    expect(screen.getByDisplayValue("35")).toBeInTheDocument()
  })
})
