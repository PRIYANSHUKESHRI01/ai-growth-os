"use client"
import { Card, CardContent } from "@/components/ui/card"
import { UploadCloud } from "lucide-react"

export default function UploadPage() {
  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-primary">Import Leads</h1>
        <p className="text-sm text-secondary mt-1">Expand your network. Upload your contacts to seamlessly map them into your kinetic growth workflows.</p>
      </div>

      <div className="grid md:grid-cols-2 gap-8">
        <div>
          <h2 className="text-xl font-semibold text-primary mb-6">Import Process</h2>
          <div className="space-y-6">
            <div className="flex gap-4">
              <div className="size-8 rounded-full bg-accent/10 flex items-center justify-center text-accent font-bold shrink-0">1</div>
              <div>
                <h3 className="font-medium text-primary">Upload File</h3>
                <p className="text-sm text-secondary mt-1">Select your CSV or XLSX file containing your lead data.</p>
              </div>
            </div>
            <div className="flex gap-4">
              <div className="size-8 rounded-full bg-accent/10 flex items-center justify-center text-accent font-bold shrink-0">2</div>
              <div>
                <h3 className="font-medium text-primary">Map Columns</h3>
                <p className="text-sm text-secondary mt-1">Match your file's headers to our system properties.</p>
              </div>
            </div>
            <div className="flex gap-4">
              <div className="size-8 rounded-full bg-accent/10 flex items-center justify-center text-accent font-bold shrink-0">3</div>
              <div>
                <h3 className="font-medium text-primary">Process & Validate</h3>
                <p className="text-sm text-secondary mt-1">We'll clean and import your leads into the database.</p>
              </div>
            </div>
          </div>
        </div>

        <Card>
          <CardContent className="p-8 h-full flex flex-col items-center justify-center text-center">
             <div className="size-16 bg-bg rounded-full flex items-center justify-center border-2 border-dashed border-border mb-4 cursor-pointer hover:border-accent transition-colors">
               <UploadCloud className="text-secondary size-6" />
             </div>
             <h3 className="text-lg font-semibold text-primary">Drag & Drop your file here</h3>
             <p className="text-sm text-secondary mt-2">Supports CSV or XLSX up to 50MB. Ensure your first row contains column headers.</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}