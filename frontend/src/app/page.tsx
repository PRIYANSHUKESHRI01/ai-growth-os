import { Navbar } from "@/components/layout/Navbar"
import { SectionWrapper } from "@/components/layout/SectionWrapper"
import { Button } from "@/components/ui/button"
import { ArrowRight, Zap, Target, BarChart3 } from "lucide-react"

export default function LandingPage() {
  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />
      <main className="flex-1">
        <SectionWrapper className="bg-bg text-center py-32 flex flex-col items-center justify-center min-h-[80vh]">
           <h1 className="text-[3.5rem] font-bold tracking-tight text-primary max-w-4xl mx-auto leading-tight">
             Execute Sales with AI Precision.
           </h1>
           <p className="text-lg text-secondary mt-6 max-w-2xl mx-auto leading-relaxed">
             The autonomous sales engine that scores leads, personalizes outreach, and closes more revenue without the manual friction.
           </p>
           <div className="flex items-center justify-center gap-4 mt-10">
             <Button variant="primary" size="lg">Start Free Trial <ArrowRight className="ml-2 size-4" /></Button>
             <Button variant="secondary" size="lg">Book Demo</Button>
           </div>
        </SectionWrapper>
        
        <SectionWrapper className="bg-card py-24">
           <div className="text-center mb-16">
             <h2 className="text-3xl font-semibold text-primary">Architected for Conversion</h2>
             <p className="text-secondary mt-4 max-w-2xl mx-auto">
               Moving beyond basic CRM. A suite of intelligent tools designed to identify and engage high-intent prospects autonomously.
             </p>
           </div>
           <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
              <div className="p-8 rounded-2xl bg-bg border border-border">
                <div className="size-12 bg-accent/10 rounded-xl flex items-center justify-center mb-6">
                  <Target className="text-accent size-6" />
                </div>
                <h3 className="text-xl font-medium text-primary mb-3">AI Lead Scoring</h3>
                <p className="text-secondary text-sm leading-relaxed">Instantly identify your highest-value prospects using predictive models trained on your successful historical conversions.</p>
              </div>
              <div className="p-8 rounded-2xl bg-bg border border-border">
                <div className="size-12 bg-accent/10 rounded-xl flex items-center justify-center mb-6">
                  <Zap className="text-accent size-6" />
                </div>
                <h3 className="text-xl font-medium text-primary mb-3">Personalized Outreach</h3>
                <p className="text-secondary text-sm leading-relaxed">Generate bespoke communication sequences tailored to the unique context and firmographics of every single lead.</p>
              </div>
              <div className="p-8 rounded-2xl bg-bg border border-border">
                <div className="size-12 bg-accent/10 rounded-xl flex items-center justify-center mb-6">
                  <BarChart3 className="text-accent size-6" />
                </div>
                <h3 className="text-xl font-medium text-primary mb-3">Automated Campaigns</h3>
                <p className="text-secondary text-sm leading-relaxed">Set up multi-channel workflows that adapt in real-time based on prospect engagement and sentiment analysis.</p>
              </div>
           </div>
        </SectionWrapper>
      </main>
      <footer className="py-8 border-t border-border bg-card text-center">
        <div className="flex justify-center gap-6 text-sm flex-wrap">
          <a href="#" className="font-medium inline-flex text-primary hover:text-accent transition-colors">Privacy Policy</a>
          <a href="#" className="font-medium inline-flex text-primary hover:text-accent transition-colors">Terms of Service</a>
          <a href="#" className="font-medium inline-flex text-primary hover:text-accent transition-colors">Security</a>
        </div>
      </footer>
    </div>
  )
}