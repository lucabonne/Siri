import * as React from "react";

type PrimitiveProps = {
  children?: React.ReactNode;
  className?: string;
  render?: React.ReactElement;
  [key: string]: unknown;
};

type PrimitiveComponent<Props = PrimitiveProps> = React.ComponentType<Props>;

export namespace Tooltip {
  export namespace Provider {
    export type Props = PrimitiveProps & { delay?: number };
  }
  export namespace Root {
    export type Props = PrimitiveProps;
  }
  export namespace Trigger {
    export type Props = PrimitiveProps;
  }
  export namespace Popup {
    export type Props = PrimitiveProps;
  }
  export namespace Positioner {
    export type Props = PrimitiveProps & {
      align?: "start" | "center" | "end";
      alignOffset?: number;
      side?: "top" | "right" | "bottom" | "left" | "inline-start" | "inline-end";
      sideOffset?: number;
    };
  }
}

export const Tooltip: {
  Provider: PrimitiveComponent<Tooltip.Provider.Props>;
  Root: PrimitiveComponent<Tooltip.Root.Props>;
  Trigger: PrimitiveComponent<Tooltip.Trigger.Props>;
  Portal: PrimitiveComponent<PrimitiveProps>;
  Positioner: PrimitiveComponent<Tooltip.Positioner.Props>;
  Popup: PrimitiveComponent<Tooltip.Popup.Props>;
  Arrow: PrimitiveComponent<PrimitiveProps>;
};
