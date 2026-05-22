import * as React from "react";

type PrimitiveProps = {
  children?: React.ReactNode;
  className?: string;
  render?: React.ReactElement;
  [key: string]: unknown;
};

type PrimitiveComponent<Props = PrimitiveProps> = React.ComponentType<Props>;

export namespace Select {
  export namespace Root {
    export type Props = PrimitiveProps;
  }
  export namespace Group {
    export type Props = PrimitiveProps;
  }
  export namespace Value {
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
      alignItemWithTrigger?: boolean;
      side?: "top" | "right" | "bottom" | "left" | "inline-start" | "inline-end";
      sideOffset?: number;
    };
  }
  export namespace GroupLabel {
    export type Props = PrimitiveProps;
  }
  export namespace Item {
    export type Props = PrimitiveProps;
  }
  export namespace Separator {
    export type Props = PrimitiveProps;
  }
  export namespace ScrollUpArrow {
    export type Props = PrimitiveProps;
  }
  export namespace ScrollDownArrow {
    export type Props = PrimitiveProps;
  }
}

export const Select: {
  Root: PrimitiveComponent<Select.Root.Props>;
  Group: PrimitiveComponent<Select.Group.Props>;
  Value: PrimitiveComponent<Select.Value.Props>;
  Trigger: PrimitiveComponent<Select.Trigger.Props>;
  Icon: PrimitiveComponent<PrimitiveProps>;
  Portal: PrimitiveComponent<PrimitiveProps>;
  Positioner: PrimitiveComponent<Select.Positioner.Props>;
  Popup: PrimitiveComponent<Select.Popup.Props>;
  List: PrimitiveComponent<PrimitiveProps>;
  GroupLabel: PrimitiveComponent<Select.GroupLabel.Props>;
  Item: PrimitiveComponent<Select.Item.Props>;
  ItemText: PrimitiveComponent<PrimitiveProps>;
  ItemIndicator: PrimitiveComponent<PrimitiveProps>;
  Separator: PrimitiveComponent<Select.Separator.Props>;
  ScrollUpArrow: PrimitiveComponent<Select.ScrollUpArrow.Props>;
  ScrollDownArrow: PrimitiveComponent<Select.ScrollDownArrow.Props>;
};
