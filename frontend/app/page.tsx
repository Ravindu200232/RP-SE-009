import DevOpsCenterPrototype from "./components/DevOpsCenterPrototype";
import IntegrationAccessCenter from "./components/IntegrationAccessCenter";

export default function HomePage() {
    return (
        <>
            <IntegrationAccessCenter />
            <DevOpsCenterPrototype showIntroOverlay={false} />
        </>
    );
}
