import * as React from "react";

type PrimitiveProps = React.ComponentPropsWithoutRef<"button"> & {
  render?: React.ReactElement;
};

export namespace Button {
  export type Props = PrimitiveProps;
}

export const Button: React.ForwardRefExoticComponent<
  Button.Props & React.RefAttributes<HTMLButtonElement>
>;
