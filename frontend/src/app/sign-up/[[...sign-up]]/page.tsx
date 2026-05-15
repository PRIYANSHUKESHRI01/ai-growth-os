import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg">
      <SignUp
        appearance={{
          elements: {
            rootBox: "shadow-2xl",
            card: "bg-card border border-border",
            headerTitle: "text-primary font-bold",
            headerSubtitle: "text-secondary",
            formButtonPrimary:
              "bg-accent hover:bg-accent/90 text-white font-medium",
            socialButtonsBlockButton:
              "border border-border text-primary hover:bg-bg/50 font-medium",
            formFieldInput:
              "bg-bg border-border text-primary placeholder:text-secondary",
            footerActionLink: "text-accent hover:text-accent/80",
          },
        }}
      />
    </div>
  );
}
