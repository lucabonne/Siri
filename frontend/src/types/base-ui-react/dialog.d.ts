import * as React from "react";

type PrimitiveProps = {
  children?: React.ReactNode;
  className?: string;
  render?: React.ReactElement;
  [key: string]: unknown;
};

type PrimitiveComponent<Props = PrimitiveProps> = React.ComponentType<Props>;

export namespace Dialog {
  export namespace Root {
    export type Props = PrimitiveProps;
  }
  export namespace Trigger {
    export type Props = PrimitiveProps;
  }
  export namespace Portal {
    export type Props = PrimitiveProps;
  }
  export namespace Close {
    export type Props = PrimitiveProps;
  }
  export namespace Backdrop {
    export type Props = PrimitiveProps;
  }
  export namespace Popup {
    export type Props = PrimitiveProps;
  }
  export namespace Title {
    export type Props = PrimitiveProps;
  }
  export namespace Description {
    export type Props = PrimitiveProps;
  }
}

export const Dialog: {
  Root: PrimitiveComponent<Dialog.Root.Props>;
  Trigger: PrimitiveComponent<Dialog.Trigger.Props>;
  Portal: PrimitiveComponent<Dialog.Portal.Props>;
  Close: PrimitiveComponent<Dialog.Close.Props>;
  Backdrop: PrimitiveComponent<Dialog.Backdrop.Props>;
  Popup: PrimitiveComponent<Dialog.Popup.Props>;
  Title: PrimitiveComponent<Dialog.Title.Props>;
  Description: PrimitiveComponent<Dialog.Description.Props>;
};
