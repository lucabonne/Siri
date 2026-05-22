import * as React from "react";

type MotionComponent<Props> = React.ComponentType<Props & { [key: string]: unknown }>;

export const motion: {
  span: MotionComponent<React.ComponentPropsWithoutRef<"span">>;
};
