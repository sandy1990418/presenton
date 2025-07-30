import React from 'react';
import { getImageSrc } from '@/utils/imageUtils';

interface OfflineImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  imageData?: {
    __image_url__?: string;
    __image_prompt__?: string;
    [key: string]: any;
  };
  src?: string;
  alt?: string;
}

/**
 * Image component that automatically handles offline/online image serving
 * Supports both imageData objects and direct src props
 */
export const OfflineImage: React.FC<OfflineImageProps> = ({
  imageData,
  src,
  alt,
  ...props
}) => {
  // Determine the image source
  const imageSrc = imageData ? getImageSrc(imageData) : (src || '/static/images/placeholder.jpg');
  
  // Determine the alt text
  const imageAlt = alt || imageData?.__image_prompt__ || 'Image';

  return (
    <img
      {...props}
      src={imageSrc}
      alt={imageAlt}
      onError={(e) => {
        // Fallback to placeholder if image fails to load
        const target = e.target as HTMLImageElement;
        if (target.src !== '/static/images/placeholder.jpg') {
          target.src = '/static/images/placeholder.jpg';
        }
        props.onError?.(e);
      }}
    />
  );
};

export default OfflineImage;