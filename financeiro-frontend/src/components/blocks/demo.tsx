import { HeroSection } from "@/components/blocks/hero-section-dark"

function HeroSectionDemo() {
  return (
    <HeroSection
      title="Bem-vindo à nossa Plataforma"
      subtitle={{
        regular: "Transforme sua gestão em ",
        gradient: "resultados excepcionais",
      }}
      description="Gerencie, acompanhe e otimize seus processos financeiros com a mais avançada suite de ferramentas e recursos."
      ctaText="Acessar o Sistema"
      ctaHref="/login"
      bottomImage={{
        light: "https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=2070&auto=format&fit=crop",
        dark: "https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=2070&auto=format&fit=crop",
      }}
      gridOptions={{
        angle: 65,
        opacity: 0.4,
        cellSize: 50,
        lightLineColor: "#4a4a4a",
        darkLineColor: "#2a2a2a",
      }}
    />
  )
}
export { HeroSectionDemo }
